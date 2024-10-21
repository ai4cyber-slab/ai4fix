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
import sys
from sast.sast_orchestrator import SASTOrchestrator
from utils.comparer import IssueComparer

class PatchGenerator:
    def __init__(self, config):
        """Initialize PatchGenerator with configuration."""
        # Load environment variables
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = openai.OpenAI()
        
        # Load configurations from file
        self.config = config
        self.project_root = self.config.get('DEFAULT', 'config.project_path')
        self.sast = SASTOrchestrator(self.config)
        # Set base directories and configurations dynamically
        self.base_dir = self.config.get('DEFAULT', 'config.project_path', fallback='')
        self.diffs_output_dir = self.config.get('DEFAULT', 'config.results_path', fallback='')
        self.json_file_path = self.config.get('ISSUES', 'config.issues_path', fallback='')
        self.warnings = []
        self.full_file_path = ""
        self.initial_content = ""

    def run_maven_test(self):
        """Run 'mvn test' command and return the result."""
        with subprocess.Popen(
            ['mvn', 'test'],
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ) as process:
            stdout, stderr = process.communicate()
            result = subprocess.CompletedProcess(args=['mvn', 'test'], returncode=process.returncode, stdout=stdout, stderr=stderr)
        return result

    def analyze_maven_output(self, result):
        """Analyze the Maven output to detect and categorize errors."""
        error_type_counts = defaultdict(int)
        returned_error_message = ""
        error_detected = False
        line_counter = 0

        # Analyze both stdout and stderr
        for output in (result.stdout, result.stderr):
            for line in output.split("\n"):
                if "[ERROR]" in line:
                    line_counter += 1
                    if line_counter == 2:  # Detect second error
                        split_line = line.split("] ")
                        error_message_key = split_line[2] if len(split_line) > 2 else split_line[1]
                        error_message = error_message_key

                        # Fetch full error message
                        next_line_index = output.split("\n").index(line) + 1
                        while next_line_index < len(output.split("\n")):
                            next_line = output.split("\n")[next_line_index]
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
        return "\n".join(code_blocks).strip() if code_blocks else response_text.strip()

    def process_warning(self, warning):
        """Process each warning, generate patches, and update JSON."""
        explanation = warning['explanation']
        items = warning['items']
        
        for item in items:
            textrange = item['textrange']
            file_path = textrange['file']
            startLine = textrange['startLine']
            endLine = textrange['endLine']
            
            full_file_path = os.path.join(self.base_dir, file_path)
            self.full_file_path = full_file_path

            # Read the file content
            try:
                with open(full_file_path, 'r') as f:
                    file_content = f.readlines()
                    initial_content = ''.join(file_content)
                    self.initial_content = initial_content
            except Exception as e:
                logger.error(f"Error reading file {full_file_path}: {e}")
                continue  # Skip to the next item

            problematic_code = ''.join(file_content[startLine-1:endLine])
            full_class_content = ''.join(file_content)

            max_attempts = 2  # We try at most twice
            attempt = 0
            patch_applied = False
            previous_generated_code = None

            while attempt < max_attempts:
                attempt += 1
                logger.info(f"Attempt {attempt} for warning ID {warning['id']}...")

                if attempt == 1:
                    # Initial prompt
                    prompt = f"""Explanation of the issue:
                    {explanation}

                    Here is the full file code:
                    ```java
                    {full_class_content}
                    The problematic code is from line {startLine} to {endLine}:
                    {problematic_code}
                    Instructions:

                    Modify only the code necessary to fix the issue described.
                    Do not alter comments, whitespace, or formatting.
                    Provide the complete updated code. """ 
                else: # Modified prompt for retry, including previous generated code 
                    initial_lines = initial_content.splitlines(keepends=True) 
                    generated_lines = previous_generated_code.splitlines(keepends=True) 
                    diff = difflib.unified_diff( initial_lines, generated_lines, fromfile='Original Code', tofile='Attempted Fix', n=0 ) 
                    diff_text = ''.join(diff)
                    # Modified prompt for retry, including diff content
                    prompt = f"""The previous attempt to fix the issue did not resolve it.
                    Here is the diff of the changes made in the last attempt:
                    {diff_text}
                    Explanation of the issue: {explanation}
                    Here is the full original file code:
                    {full_class_content}
                    Instructions:

                    Analyze the previous attempt and identify why it did not fix the issue.
                    Modify only the code necessary to fix the issue described.
                    Do not alter comments, whitespace, or formatting.
                    Provide the complete updated code only. """
                    
                os.makedirs(self.diffs_output_dir, exist_ok=True)
                response = self.call_openai_with_retries(prompt)

                if response is None:
                    logger.error(f"Failed to get response from OpenAI. Creating backup patch.")
                    sample_patch_path = self.create_sample_patch(file_path, warning)
                    
                    # Ensure the 'patches' list exists and append the patch details
                    if 'patches' not in item:
                        item['patches'] = []
                    item['patches'].append({
                        "path": sample_patch_path,
                        "explanation": "Backup patch generated due to failed OpenAI patch generation."
                    })
                    break  # Cannot proceed without a response

                generated_code = self.extract_code_from_response(response.choices[0].message.content)
                previous_generated_code = generated_code  # Store for next attempt if needed

                try:
                    with open(full_file_path, 'w') as f:
                        f.write(generated_code)
                except Exception as e:
                    logger.error(f"Error writing to file {full_file_path}: {e}")
                    continue

                logger.info(f"Running 'mvn test' for warning ID {warning['id']}...")
                result = self.run_maven_test()
                error_detected, _, _ = self.analyze_maven_output(result)
                if error_detected:
                    logger.error(f"Maven tests failed. Retrying...")
                    # Restore initial content before retrying
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Reverted {full_file_path} to its initial content due to Maven test failure.")
                    except Exception as e:
                        logger.error(f"Error restoring original content to {full_file_path}: {e}")
                    continue  # Retry if mvn test fails

                logger.info(f"Maven tests passed.")
                
                sast_passed = self.sast_validation(file_path, warning)
                if sast_passed:
                    logger.info(f"SAST validation passed.")
                    diff = difflib.unified_diff(
                        initial_content.splitlines(keepends=True),
                        generated_code.splitlines(keepends=True),
                        fromfile=file_path,
                        tofile=file_path,
                        n=0
                    )
                    diff_text = ''.join(diff)

                    diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}_attempt_{attempt}.diff"
                    diff_file_path = os.path.join(self.diffs_output_dir, diff_file_name)
                    try:
                        with open(diff_file_path, 'w') as diff_file:
                            diff_file.write(diff_text)
                    except Exception as e:
                        logger.error(f"Error writing diff to file {diff_file_path}: {e}")

                    # Ensure the 'patches' list exists and append the patch details
                    if 'patches' not in item:
                        item['patches'] = []
                    item['patches'].append({
                        "path": diff_file_name,
                        "explanation": explanation
                    })
                    patch_applied = True
                    break  # Exit the retry loop since we succeeded
                else:
                    logger.error(f"SAST validation failed.")
                    # Restore initial content before retrying
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Reverted {full_file_path} to its initial content due to SAST validation failure.")
                    except Exception as e:
                        logger.error(f"Error restoring original content to {full_file_path}: {e}")

                    if attempt >= max_attempts:
                        logger.error(f"Maximum attempts reached for warning ID {warning['id']}.")
                    else:
                        logger.info(f"Retrying for warning ID {warning['id']}...")

            # After all attempts, ensure the initial content is restored
            try:
                with open(full_file_path, 'w') as f:
                    f.write(initial_content)
                    logger.info(f"Final restoration of {full_file_path} to its initial content.")
            except Exception as e:
                logger.error(f"Error restoring original content to {full_file_path}: {e}")

            if not patch_applied:
                logger.error(f"Failed to generate a valid patch for warning ID {warning['id']} after {max_attempts} attempts.")
                # Optionally, record that no patch was applied
                if 'patches' not in item:
                    item['patches'] = []
            

    def create_sample_patch(self, java_file_path, warning):
        """Create a sample patch file with the Java file path and warning ID using coordinates from the warning."""
        warning_id = warning.get('id', 'unknown_id') # Get the ID from the warning, fallback to 'unknown_id' 
        sample_patch_name = f"{warning_id}_backup_patch.diff" 
        sample_patch_path = os.path.join(self.diffs_output_dir, sample_patch_name)
        textrange = warning['items'][0]['textrange']  # Assuming textrange is in the first item of items
        start_line = textrange.get('startLine', 0)
        end_line = textrange.get('endLine', 1)
        start_column = textrange.get('startColumn', 0)
        end_column = textrange.get('endColumn', 1)

                # Create the patch content using the extracted coordinates
        with open(sample_patch_path, 'w') as sample_patch:
                sample_patch.write(f"--- {java_file_path}\n")
                sample_patch.write(f"+++ {java_file_path}\n")
                sample_patch.write(f"@@ -{start_line},{start_column} +{end_line},{end_column} @@\n")
                sample_patch.write(f"+// This is a Backup patch for {java_file_path}\n")

        return sample_patch_name
    

    def sast_validation(self, file_path, warning):
        try:
            self.sast.run_all(validation=True, java_file_path=file_path)
            original_json_sast = self.config.get("ISSUES", "config.sast_issues_path", fallback=os.path.join(self.config.get("ISSUES", "config.issues_path").replace("issues.json", "sast_issues.json"))) 
            temp_json_sast = os.path.join(self.config.get("ISSUES", "config.issues_path").replace("issues.json", "sast_validation_issues.json")) 
            self.comparer = IssueComparer(original_json_sast, temp_json_sast, file_path) 
            # Perform the comparison 
            self.comparer.compare_issues()
            # Get the results
            removed_ids = self.comparer.get_removed_issue_ids()
            existing_ids = self.comparer.get_existing_issue_ids()
            # print(f"Issues removed after applying patch no: {warning['id']} -> {removed_ids}")
            # print(f"Issues still present after applying patch no: {warning['id']} -> {existing_ids}")
            if warning['id'] in removed_ids:
                return True
            else:
                if warning['id'] not in existing_ids:
                    return True
                return False
        except Exception as e:
            logger.error("An error occured during SAST Validation")
        finally:
            try:
                with open(self.full_file_path, 'w') as f:
                    f.write(self.initial_content)
            except Exception as e:
                logger.error(f"Error restoring original content to {self.full_file_path}: {e}")
                return
        
    def main(self):
        try: 
            if not openai.api_key: 
                logger.warning("OPENAI_API_KEY is not set. Skipping patch generation.") 
                return
            # Load the issues JSON file
            try:
                with open(self.json_file_path, 'r') as f:
                    self.warnings = json.load(f)
            except Exception as e:
                logger.error(f"Error reading warnings JSON: {e}")
                return

            logger.info("Patch Generation Started...")
            start_time = time.time()

            # Process each warning
            for warning in self.warnings:
                logger.info(f"Processing warning ID {warning['id']}...")
                try:
                    self.process_warning(warning)
                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt detected. Stopping the script gracefully.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error processing warning ID {warning['id']}: {e}")
                    continue  # Continue with the next warning
                logger.info(f"Finished processing warning ID {warning['id']}.")

            # Save the updated warnings with patches to the issues.json file
            try:
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.warnings, f, indent=4)  # Save with pretty-printing
            except Exception as e:
                logger.error(f"Error saving updated issues JSON: {e}")

            elapsed_time = time.time() - start_time
            logger.info(f"Patch generation completed in {elapsed_time:.2f} seconds")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt detected. Stopping the script gracefully.")
            return
        finally:
            # Ensure the initial content is restored
            try:
                logger.info(f"Restoring original content to {self.full_file_path}.")
                with open(self.full_file_path, 'w') as f:
                    f.write(self.initial_content)
            except Exception as e:
                logger.error(f"Error restoring original content to {self.full_file_path}: {e}")
                return
        
    def call_openai_with_retries(self, prompt, max_retries=3):
        try:
            """Call OpenAI API with retry logic and handle keyboard interrupt."""
            retries = 0
            while retries < max_retries:
                try:
                    response = self.client.chat.completions.create(
                        model=f"{self.config.get('CLASSIFIER', 'gpt_model')}",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that can fix code issues."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    return response
                except openai.APIConnectionError as e:
                    logger.error(f"Connection error: {e}, retrying...")
                except openai.AuthenticationError as e:
                    logger.error(f"Authentication error: {e}, retrying...")
                    return None
                except openai.Timeout as e:
                    logger.error(f"Timeout error: {e}, retrying...")
                except openai.RateLimitError as e:
                    logger.error(f"Rate limit exceeded: {e}, retrying after delay...")
                    time.sleep(4)
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    break
                retries += 1
                time.sleep(2 ** retries + random.uniform(0, 1))
        except Exception as e:
            return None