import os
import json
import subprocess
import openai
from dotenv import load_dotenv, find_dotenv
from utils.logger import logger
from collections import defaultdict
import re
import difflib
import time

class PatchGenerator:
    def __init__(self, config):
        """Initialize PatchGenerator with config."""
        # Load environment variables
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = openai.OpenAI()  # Corrected to use openai directly
                
        # Load configurations from file
        self.config = config
                
        # Set base directories and configurations dynamically
        self.base_dir = self.config.get('DEFAULT', 'config.project_path', fallback='')
        self.project_root = self.config.get('DEFAULT', 'config.project_path')
        self.diffs_output_dir = self.config.get('DEFAULT', 'config.results_path', fallback='')
        self.json_file_path = self.config.get('ISSUES', 'config.issues_path', fallback='')
        self.warnings = []

    def run_maven_clean_test(self):
        """Run 'mvn clean test' command and return the result."""
        result = subprocess.run(
            ['mvn', 'clean', 'test'],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        return result

    def analyze_maven_output(self, result):
        """Analyze the Maven output to detect and categorize errors."""
        error_type_counts = defaultdict(int)
        error_message_key = ""
        returned_error_message = ""
        error_detected = False

        line_counter = 0

        for line in result.stdout.split("\n"):
            if "[ERROR]" in line:
                line_counter += 1
                if line_counter == 2:
                    split_line = line.split("] ")
                    if len(split_line) > 2:
                        error_message_key = split_line[2]
                        error_message = error_message_key
                    else:
                        error_message = split_line[1]
                    
                    lines = result.stdout.split("\n")
                    next_line_index = lines.index(line) + 1
                    while next_line_index < len(lines):
                        next_line = lines[next_line_index]
                        if next_line.startswith("[ERROR]") or next_line.startswith("[INFO]"):
                            break
                        error_message += "\n" + next_line
                        next_line_index += 1
                    
                    returned_error_message = error_message
                    error_type_counts[error_message_key] += 1
                    error_detected = True
                    break

        for line in result.stderr.split("\n"):
            if "[ERROR]" in line:
                line_counter += 1
                if line_counter == 2:
                    split_line = line.split("] ")
                    if len(split_line) > 2:
                        error_message_key = split_line[2]
                        error_message = error_message_key
                    else:
                        error_message = split_line[1]
                    
                    lines = result.stderr.split("\n")
                    next_line_index = lines.index(line) + 1
                    while next_line_index < len(lines):
                        next_line = lines[next_line_index]
                        if next_line.startswith("[ERROR]") or next_line.startswith("[INFO]"):
                            break
                        error_message += "\n" + next_line
                        next_line_index += 1

                    returned_error_message = error_message
                    error_type_counts[error_message_key] += 1
                    error_detected = True
                    break

        return error_detected, error_type_counts, returned_error_message

    def extract_code_from_response(self, response_text):
        """Extract the Java code from the AI response."""
        code_blocks = re.findall(r'```(?:java|Java)?\s*(.*?)\s*```', response_text, re.DOTALL)
        if code_blocks:
            return "\n".join(code_blocks).strip()
        return response_text.strip()

    def process_diff(self, diff_text):
        """Process the diff to exclude comment-only changes."""
        lines = diff_text.splitlines(keepends=True)
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('@@'):
                # Start of a hunk
                hunk_lines = []
                hunk_lines.append(line)
                i += 1
                while i < len(lines) and not lines[i].startswith('@@'):
                    hunk_lines.append(lines[i])
                    i += 1
                # Process the hunk
                processed_hunk = self.process_hunk(hunk_lines)
                if processed_hunk:
                    new_lines.extend(processed_hunk)
                # If the processed hunk is empty, it's skipped
            else:
                # Header lines
                new_lines.append(line)
                i += 1
        # Return the modified diff text
        return ''.join(new_lines)

    def is_comment_line(self, content):
        """Determine if a line is a comment or empty."""
        stripped_content = content.strip()
        # Check for single-line and multi-line comments
        return re.match(r'^(\s*(//|/\*|\*|\*/|#))|^\s*$', stripped_content) is not None

    def process_hunk(self, hunk_lines):
        """Process a single hunk of the diff."""
        output_lines = []
        # Keep the hunk header
        output_lines.append(hunk_lines[0])
        lines = hunk_lines[1:]
        line_tuples = []
        for line in lines:
            if line.startswith('-') or line.startswith('+') or line.startswith(' '):
                line_tuples.append((line[0], line[1:].rstrip('\n')))
            else:
                line_tuples.append(('', line.rstrip('\n')))

        processed_line_tuples = []
        all_changes_are_comments = True  # Flag to determine if all changes are comments
        i = 0
        while i < len(line_tuples):
            line_type, content = line_tuples[i]
            content_stripped = content.strip()
            if line_type in ('-', '+'):
                # Skip empty or whitespace-only lines
                if content_stripped == '':
                    i += 1
                    continue
                else:
                    # Check if the line is a comment
                    if self.is_comment_line(content):
                        # Line is a comment, skip it
                        i += 1
                        continue
                    else:
                        # Line is not a comment
                        all_changes_are_comments = False
                        # Keep the line
                        processed_line_tuples.append((line_type, content))
                        i += 1
            else:
                # Context line, keep it
                processed_line_tuples.append((line_type, content))
                i += 1

        # If all changes are comments or no changes remain, exclude the hunk
        change_lines = [lt for lt in processed_line_tuples if lt[0] in ('-', '+')]
        if not change_lines or all_changes_are_comments:
            # Hunk has no relevant changes after processing
            return []
        else:
            for line_type, content in processed_line_tuples:
                if line_type in ('-', '+', ' '):
                    output_lines.append(line_type + content + '\n')
                else:
                    # Line was marked for removal; skip it
                    pass
            return output_lines

    def process_warning(self, warning):
        """Process a single warning to generate and apply patches."""
        explanation = warning['explanation']
        items = warning['items']
        
        for item in items:
            textrange = item['textrange']
            file_path = textrange['file']
            startLine = textrange['startLine']
            endLine = textrange['endLine']
            
            full_file_path = os.path.join(self.base_dir, file_path)
            file_relative_path = os.path.relpath(full_file_path, self.base_dir)
            
            # Read the file content
            try:
                with open(full_file_path, 'r') as f:
                    file_content = f.readlines()
                    initial_content = ''.join(file_content)
            except Exception as e:
                logger.error(f"Error reading file {full_file_path}: {e}")
                continue  # Skip to the next item
            
            # Extract the problematic code
            problematic_code = ''.join(file_content[startLine-1:endLine])
            
            # Get the full file content
            full_class_content = ''.join(file_content)

            # Prepare the prompt for the AI model
            prompt = f"""Explanation of the issue:
            {explanation}

            Here is the full file code:

            ```java
            {full_class_content}
            ```
            The problematic code is from line {startLine} to {endLine}:

            ```java
            {problematic_code}
            ```
            Please modify the code to fix the issue described in the explanation.
            Provide the complete updated code of the file, and do not include any explanations or comments.
            Ensure that the code compiles and maintains the original functionality except for the fix."""
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that can fix code issues."},
                        {"role": "user", "content": prompt}
                    ]
                )
                generated_code = self.extract_code_from_response(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"Error calling OpenAI API: {e}")
                continue
            
            # Write the generated code to the file
            try:
                with open(full_file_path, 'w') as f:
                    f.write(generated_code)
            except Exception as e:
                logger.error(f"Error writing to file {full_file_path}: {e}")
                continue
            
            # Run 'mvn clean test'
            logger.info(f"Running 'mvn clean test' for warning ID {warning['id']}...")
            result = self.run_maven_clean_test()
            
            # Analyze Maven output
            error_detected, error_type_counts, returned_error_message = self.analyze_maven_output(result)
            
            os.makedirs(self.diffs_output_dir, exist_ok=True)

            if not error_detected:
                logger.info(f"Maven tests passed.")
                # Generate diff between initial and modified content
                diff = difflib.unified_diff(
                    initial_content.splitlines(keepends=True),
                    generated_code.splitlines(keepends=True),
                    fromfile= f"{file_path}",
                    tofile= f"{file_path}",
                    n=3
                )
                diff_text = ''.join(diff)

                # Optionally, write the raw diff for debugging
                raw_diff_file = os.path.join(self.diffs_output_dir, f"{os.path.splitext(os.path.basename(full_file_path))[0]}_raw_patch_{warning['id']}.diff")
                try:
                    with open(raw_diff_file, 'w') as diff_file:
                        diff_file.write(diff_text)
                except Exception as e:
                    logger.error(f"Error writing raw diff to file {raw_diff_file}: {e}")

                # Process the diff to exclude comment-only changes
                processed_diff_text = self.process_diff(diff_text)

                # Save the processed diff to a file
                diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}.diff"
                diff_file_path = os.path.join(self.diffs_output_dir, diff_file_name)
                try:
                    with open(diff_file_path, 'w') as diff_file:
                        diff_file.write(processed_diff_text)
                except Exception as e:
                    logger.error(f"Error writing processed diff to file {diff_file_path}: {e}")

                # Add the patch to the warning's patches
                if 'patches' not in item:
                    item['patches'] = []
                item['patches'].append({
                    "path": diff_file_name,
                    "explanation": explanation
                })

                # Write updated warnings to the JSON file
                try:
                    with open(self.json_file_path, 'w') as f:
                        json.dump(self.warnings, f, indent=4)
                except Exception as e:
                    logger.error(f"Error writing updated warnings to JSON file: {e}")
            else:
                logger.error(f"Maven tests failed.")
            
            # Revert the file to its initial content
            try:
                with open(full_file_path, 'w') as f:
                    f.write(initial_content)
                    logger.info(f"Reverted {full_file_path} to its initial content.")
            except Exception as e:
                logger.error(f"Error restoring original content to {full_file_path}: {e}")

    def main(self):
        """Main method to initiate patch generation."""
        if not openai.api_key:
            logger.warning("OPENAI_API_KEY is not set. Skipping the patch generation process.")
            return
        # Read the JSON file containing warnings
        try:
            with open(self.json_file_path, 'r') as f:
                self.warnings = json.load(f)
        except Exception as e:
            logger.error(f"Error reading warnings JSON file: {e}")
            return
        
        # Process each warning
        logger.info(f"Patch Generation Started ...\n")
        start_time = time.time()
        for warning in self.warnings:
            logger.info(f"Processing warning ID {warning['id']}...")
            self.process_warning(warning)
            logger.info(f"Finished processing warning ID {warning['id']}.\n")
        elapsed_time = time.time() - start_time
        logger.info(f"Patch generation completed in {elapsed_time:.2f} seconds\n")