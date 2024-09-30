import os
import json
import subprocess
import openai
from dotenv import load_dotenv, find_dotenv
from collections import defaultdict
from utils.logger import logger
import re
import difflib
import time
import random

class PatchGenerator:
    def __init__(self, config):
        """Initialize CodeFixer with config."""
        # Load environment variables
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = openai.OpenAI()
            
        # Load configurations from file
        self.config = config
            
        # Set base directories and configurations dynamically
        self.base_dir = self.config.get('DEFAULT', 'config.project_path', fallback='')
        self.project_root = self.config.get('DEFAULT', 'config.project_path')
        self.diffs_output_dir = self.config.get('DEFAULT', 'config.results_path', fallback='')
        self.json_file_path = self.config.get('ISSUES', 'config.issues_path', fallback='')
        self.warnings = []

    # def run_maven_clean_test(self):
    #     """Run 'mvn clean test' command and return the result."""
    #     result = subprocess.run(
    #         ['mvn', 'clean', 'test'],
    #         cwd=self.project_root,
    #         capture_output=True,
    #         text=True
    #     )
    #     return result
    def run_maven_test(self):
        """Run 'mvn test' command and return the result."""
        result = subprocess.run(
            ['mvn', 'test'],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        return result
    # javac path/to/YourClass.java

    # def compile_java_file(self, java_file_path):
    #     """Run 'mvn test' command and return the result."""
    #     result = subprocess.run(
    #         ['javac', rf'{java_file_path}'],
    #         cwd=self.project_root,
    #         capture_output=True,
    #         text=True
    #     )
    #     return result



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

    def process_warning(self, warning):
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
                    
                    Instructions:

                    - Modify only the code necessary to fix the issue described in the explanation.
                    - Do not alter any other parts of the code, including comments, whitespace, or formatting.
                    - Provide the complete updated code of the file with the changes required.
                    - Ensure that the code compiles and maintains the original functionality except for the fix.
                    """
            try:
                response = self.call_openai_with_retries(prompt)
                if response is None:
                    logger.error(f"Failed to get a response from OpenAI after retries.")
                    continue
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
            result = self.run_maven_test()
            
            # Analyze Maven output
            error_detected, error_type_counts, returned_error_message = self.analyze_maven_output(result)
            
            os.makedirs(self.diffs_output_dir, exist_ok=True)

            if not error_detected:
                logger.info(f"Maven tests passed.")
                # file_name = os.path.basename(file_path)
                # Generate diff between initial and modified content
                diff = difflib.unified_diff(
                    initial_content.splitlines(keepends=True),
                    generated_code.splitlines(keepends=True),
                    fromfile= f"{file_path}",
                    tofile= f"{file_path}",
                    n=3
                )
                diff_text = ''.join(diff)

                # Save the diff to a file
                diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}.diff"
                diff_file_path = os.path.join(self.diffs_output_dir, diff_file_name)
                try:
                    with open(diff_file_path, 'w') as diff_file:
                        diff_file.write(diff_text)
                except Exception as e:
                    logger.error(f"Error writing diff to file {diff_file_path}: {e}")

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
            try:
                with open(full_file_path, 'w') as f:
                    f.write(initial_content)
                    logger.info(f"Reverted {full_file_path} to its initial content.")
            except Exception as e:
                logger.error(f"Error restoring original content to {full_file_path}: {e}")

    def main(self):
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


    def call_openai_with_retries(self, prompt, max_retries=5):
        """Call OpenAI API with retry logic."""
        retries = 0
        while retries < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that can fix code issues."},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response
            except openai.APIConnectionError as e:
                logger.error(f"Connection error: {e}, retrying...")
            except openai.Timeout as e:
                logger.error(f"Timeout error: {e}, retrying...")
            except openai.RateLimitError as e:
                logger.error(f"Rate limit exceeded: {e}, retrying after delay...")
                time.sleep(4)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break
            
            retries += 1
            sleep_time = 2 ** retries + random.uniform(0, 1)
            time.sleep(sleep_time)
        return None