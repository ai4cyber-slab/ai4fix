import os
import json
import subprocess
import openai
from dotenv import load_dotenv, find_dotenv
from utils.logger import logger
import re
import time
import random
from sast.sast_orchestrator import SASTOrchestrator
from symbolic_execution.execution import SymbolicExecution
from patch_generation.sast_mapping import SAST_WARNINGS
from utils.findMethod import get_method_info_if_any
from groq import Groq
from patch_generation.mesure import BenchmarkVisualizer
import statistics

class PatchGenerator:
    def __init__(self, config, warning_dict, num_of_rounds):
        """Initialize PatchGenerator with configuration."""
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = openai.OpenAI()
        self.client2 = Groq(
            api_key="key"
        )
        self.config = config
        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.sast = SASTOrchestrator(self.config)
        self.symbolic = SymbolicExecution(self.config)
        self.visualize_path = os.path.join(self.project_path, '.ai4framework', 'visualizations')
        self.base_dir = self.project_path
        self.diffs_output_dir = self.config.get('DEFAULT', 'config.results_path')
        self.json_file_path = self.config.get('DEFAULT', 'config.issues_path')
        self.model_name = self.config.get("CLASSIFIER", "gpt_model")
        self.warnings = []
        self.full_file_path = ""
        self.initial_content = ""
        self.compilation_or_test_errors = 0
        self.validation_errors = 0
        self.successful_patches = 0
        self.non_applicabale_diffs = 0
        self.validation_passed = True
        self.mvn_test_passed = True
        self.applicable_patch = True
        self.input_tokens = []
        self.response_tokens = []

        self.stats = {
            'total_issues': 0,
            'build_failures': 0,
            'validation_failures': 0,
            'successful_patches': 0,
            'non_applicabale_diffs': 0,
            'total_attempts': 0,
            'prompt_tokens': 0,
            'response_tokens': 0,
            'original_warnings_dict': {},
            'elapsed_time': 0.0
        }
        self.num_of_rounds = num_of_rounds
        self.visualizer = BenchmarkVisualizer(num_of_rounds)


        self.warnings_dict = warning_dict
        self.mutable_warnings = warning_dict.copy()

    def run_maven_test(self):
        """Run 'mvn test' command and return the result."""
        with subprocess.Popen(
            ['mvn','clean', 'test'],
            cwd=self.project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ) as process:
            stdout, stderr = process.communicate()
            result = subprocess.CompletedProcess(args=['mvn', 'clean', 'test'], returncode=process.returncode, stdout=stdout, stderr=stderr)
        return result

    def analyze_maven_output(self, result):
        """Analyze the Maven output to detect and categorize errors."""
        error_detected = False

        for line in result.stdout.split("\n"):
            if "BUILD FAILURE" in line or "[ERROR] COMPILATION ERROR :" in line:
                error_detected = True
        return error_detected
    

    def extract_patch_from_response(self, response_text):
        """Extract content from any block in triple backticks from the AI response."""
        content_blocks = re.findall(r'```(?:[^\s]*)?\s*(.*?)\s*```', response_text, re.DOTALL)
        return "\n".join(content_blocks).strip() if content_blocks else response_text.strip()
    
    def code_file_to_json(self, java_file_path):
        with open(java_file_path, 'r') as java_file:
            lines = java_file.readlines()
        lines_dict = {"Line:"+str(i + 1): line.rstrip() if line.strip() else '' for i, line in enumerate(lines)}
        json_output = json.dumps(lines_dict, indent=2)
        return json_output
    
    def extract_json_section(self, json_output, start_key, end_key):
        lines_dict = json.loads(json_output)
        start_index = list(lines_dict.keys()).index(start_key)
        end_index = list(lines_dict.keys()).index(end_key)
        extracted_dict = dict(list(lines_dict.items())[start_index:end_index + 1])
        extracted_json = json.dumps(extracted_dict, indent=2)
        return extracted_json
    
    def apply_patch_from_text(self, file_path, patch_text, extractedJson):
        """Apply a patch to a file using the `patch` command with patch content provided as text."""
        try:
            patch_text_ = self.update_json_with_diff(extractedJson, patch_text)
            result = subprocess.run(
                ['patch', '-f', '--fuzz=3', '--ignore-whitespace', '--no-backup-if-mismatch', '--reject-file=/dev/null', file_path],
                input=patch_text,
                text=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("Patch applied successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to apply patch.")
            return False
        
    def adjust_patch_content(self, patch_content):
        updated_patch_lines = []
        lines = patch_content.splitlines()
        
        hunk_header_pattern = re.compile(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@')
        current_hunk_lines = []
        inside_hunk = False
        header_info = None
        
        for line in lines:
            match = hunk_header_pattern.match(line)
            if match:

                if inside_hunk:
                    updated_patch_lines.extend(self.process_hunk(current_hunk_lines, header_info))
                    current_hunk_lines = []
                
 
                header_info = match.groups()
                inside_hunk = True
            elif inside_hunk:
                current_hunk_lines.append(line)

                if line.startswith('@@') or line == lines[-1]:
                    inside_hunk = False
                    updated_patch_lines.extend(self.process_hunk(current_hunk_lines, header_info))
                    current_hunk_lines = []
                    if line != lines[-1]:
                        updated_patch_lines.append(line)
            else:
                updated_patch_lines.append(line)
        

        if inside_hunk:
            updated_patch_lines.extend(self.process_hunk(current_hunk_lines, header_info))
        
        return '\n'.join(updated_patch_lines)

    def process_hunk(self, hunk_lines, header_info):
        original_line_count = int(header_info[1])
        new_line_count = int(header_info[3])
        

        context_lines = 0
        added_lines = 0
        removed_lines = 0
        
        for line in hunk_lines:
            if line.startswith('-'):
                removed_lines += 1
            elif line.startswith('+'):
                added_lines += 1
            else:
                context_lines += 1
        

        new_original_line_count = context_lines + removed_lines
        new_new_line_count = context_lines + added_lines

        updated_header = f"@@ -{header_info[0]},{new_original_line_count} +{header_info[2]},{new_new_line_count} @@"
        

        return [updated_header] + hunk_lines + ['']
    


    def process_warning(self, warning):
        """Process each warning, generate patches, and update JSON."""
        explanation = warning['explanation']
        items = warning['items']
        name = warning['name']
        tag = warning['tags']
        
        for item in items:
            textrange = item['textrange']
            file_path = textrange['file']
            startLine = textrange['startLine']
            endLine = textrange['endLine']
            
            full_file_path = os.path.join(self.base_dir, file_path)
            self.full_file_path = full_file_path
            code_in_json_format = self.code_file_to_json(self.full_file_path)


            try:
                with open(full_file_path, 'r') as f:
                    file_content = f.readlines()
                    initial_content = ''.join(file_content)
                    self.initial_content = initial_content
            except Exception as e:
                logger.error(f"Error reading file {full_file_path}: {e}")
                continue

            max_attempts = 2
            attempt = 0
            patch_applied = False
            previous_generated_patch = None
            SOLVE_COMMAND = SAST_WARNINGS.get(name, explanation)
            METHOD_INFO, METHOD_START, METHOD_END = get_method_info_if_any(code_in_json_format, startLine, endLine)
            adjusted_start_line = int(startLine) - 1
            adjusted_end_line = int(endLine) + 1
            if f"Line:{adjusted_start_line}" in code_in_json_format and f"Line:{adjusted_end_line}" in code_in_json_format:
                extract_json_section = self.extract_json_section(code_in_json_format, f"Line:{adjusted_start_line}", f"Line:{adjusted_end_line}")
            else:
                extract_json_section = self.extract_json_section(code_in_json_format, f"Line:{startLine}", f"Line:{endLine}")

            if METHOD_START and METHOD_END:
                extract_json_section = self.extract_json_section(code_in_json_format, f"Line:{METHOD_START}", f"Line:{METHOD_END}")

            while attempt < max_attempts:
                attempt += 1
                logger.info(f"Attempt {attempt} for warning ID {warning['id']}...")
                if attempt == 1:
                    prompt = f"""
                    Please follow these instructions:
                    1. Patch Output Requirements:
                    Provide the output in .patch format and only that no further explination is needed.
                    the hunk header should reflect the line where the change occurs use the json keys which are the correct line numbers of original file, don't use much context only content with - or +.
                    Ensure each hunk starts with the correct hunk header in the format: @@ -<line_number>,<context_lines> +<line_number>,<context_lines> @@.
                    Also patch should start with the source and destination paths which are the same that will have the change with +++ and --- only and no extra metadata: {file_path}
                    2. Change Request:
                    Please fix this warning coming from static analysis tool in a creative logical way like a sofwtare engineer with +15 years of experience but Provide only the updated lines with + or - signs and no additional context lines: {explanation}
                    The issue starts from line {startLine} and ends in line {endLine}.
                    Solve that issue by: {SOLVE_COMMAND} {METHOD_INFO}
                    Format the patch strictly according to the specified guidelines.
                    ```json
                    {extract_json_section}
                    ```
                    Please validate the patch for syntax correctness if the patch is applied before providing it.
                    Make sure If any part of a method needs updating if it relates to the warning, please remove the entire method using - signs and add the updated method with + signs, ensuring it is surrounded by parentheses.
                    """
                else:
                    prompt = f"""The previous attempt to fix the issue did not resolve it.
                    Here is the patch you gave me in last attempt:
                    {previous_generated_patch}
                    Explanation of the issue: {explanation}
                    the issue is between line {startLine} and line {endLine}
                    Here is the full original file code in json format with lines as the keys use them when providing the patch accurately:
                    {extract_json_section}
                    Instructions:
                    Analyze the previous attempt and identify why it did not fix the issue.
                    Solve it by: {SOLVE_COMMAND} {METHOD_INFO}
                    The patch should start with the source and destination paths which are the same that will have the change with +++ and --- only and no extra metadata: {file_path}
                    Modify only the parts necessary to fix the issue described use the keys from the json.
                    Provide the output in .patch format and only that no further explination is needed.
                    """
                    
                os.makedirs(self.diffs_output_dir, exist_ok=True)
                # response = self.call_openai_with_retries(prompt)
                response = self.call_llama3_with_retries(prompt)


                if response is None:
                    logger.error(f"Failed to get response.")
                    break
                generated_patch = self.extract_patch_from_response(response.choices[0].message.content)
                previous_generated_patch = generated_patch
                try:
                    if not self.apply_patch_from_text(self.full_file_path, self.adjust_patch_content(generated_patch), extract_json_section):
                        self.applicable_patch = False
                        self.validation_passed = True
                        self.mvn_test_passed = True
                        try:
                            with open(full_file_path, 'w') as f:
                                f.write(initial_content)
                        except Exception as e:
                            logger.error(f"Error while restoring original content to {full_file_path}: {e}")
                        continue
                except Exception as e:
                    logger.error(e)
                    continue



                logger.info(f"Running 'mvn test' for warning ID {warning['id']}...")
                result = self.run_maven_test()
                error_detected = self.analyze_maven_output(result)
                if error_detected:
                    self.applicable_patch = True
                    self.validation_passed = True
                    self.mvn_test_passed = False
                    logger.warning(f"Maven tests failed. Retrying...")
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Reverted {full_file_path} to its initial content due to Maven test failure.")
                    except Exception as e:
                        logger.error(f"Error restoring original content to {full_file_path}: {e}")
                    continue

                logger.info(f"Maven tests passed.")
                
                self.validation_passed = self.tools_validation(name, tag)
                if self.validation_passed:
                    self.applicable_patch = True
                    self.validation_passed = True
                    self.mvn_test_passed = True
                    self.input_tokens.append(response.usage.prompt_tokens)
                    self.response_tokens.append(response.usage.completion_tokens)
                    diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}_attempt_{attempt}.diff"
                    diff_file_path = os.path.join(self.diffs_output_dir, diff_file_name)
                    try:
                        with open(diff_file_path, 'w') as diff_file:
                            diff_file.write(generated_patch)
                    except Exception as e:
                        logger.error(f"Error writing diff to file {diff_file_path}: {e}")

                    if 'patches' not in item:
                        item['patches'] = []
                    item['patches'].append({
                        "path": diff_file_name,
                        "explanation": explanation
                    })
                    patch_applied = True
                    self.successful_patches += 1
                    self.warnings_dict[name] -= 1
                    break
                else:
                    self.applicable_patch = True
                    self.validation_passed = False
                    self.mvn_test_passed = True
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Reverted {full_file_path} to its initial content due to validation failure.")
                    except Exception as e:
                        logger.error(f"Error restoring original content to {full_file_path}: {e}")

                    if attempt >= max_attempts:
                        logger.warning(f"Maximum attempts reached for warning ID {warning['id']}.")
                    else:
                        logger.info(f"Retrying for warning ID {warning['id']}...")

            try:
                with open(full_file_path, 'w') as f:
                    f.write(initial_content)
            except Exception as e:
                logger.error(f"Error restoring original content to {full_file_path}: {e}")

            if not patch_applied:
                logger.error(f"Failed to generate a valid patch for warning ID {warning['id']} after {max_attempts} attempts.")

                if 'patches' not in item:
                    item['patches'] = []
            if self.applicable_patch == False:
                self.non_applicabale_diffs += 1
            if  self.validation_passed == False:
                self.validation_errors += 1
            if  self.mvn_test_passed == False:
                self.compilation_or_test_errors += 1
            self.stats['total_attempts'] += attempt



    def tools_validation(self, name, tag):
        """
        Run validation to ensure the patch is valid using symbolic execution or specific SAST tools based on the tag.

        Args:
            file_path (str): Path to the file being validated.
            name (str): Name of the issue being validated.
            tag (str): Tag specifying the tool to use ("SE" for symbolic execution, "SB" for SpotBugs, "PMD" for PMD, or None for all SAST tools).

        Returns:
            bool: True if validation passed (warning count reduced or no warnings remain), False otherwise.
        """
        logger.info(f"Running validation for {name} with tag '{tag}' ...")

        try:
            if tag == "SE":
                logger.info("Using symbolic execution tool for validation.")
                after = self.symbolic.analyze(validation=True)
            elif tag == "SB":
                logger.info("Using SpotBugs tool for validation.")
                after = self.sast.run_all(validation=True, tool="SB")
            elif tag == "PMD":
                logger.info("Using PMD tool for validation.")
                after = self.sast.run_all(validation=True, tool="PMD")
            else:
                logger.info("Using all SAST tools for validation.")
                after = self.sast.run_all(validation=True)

            before = self.mutable_warnings

            if name in after:
                if before[name] > after[name]:
                    logger.info("Validation passed: warning count reduced.")
                    return True
                else:
                    logger.warning("Validation failed: warning count did not reduce.")
                    return False
            else:
                logger.info("Validation passed: no remaining warnings for this issue.")
                return True

        except Exception as e:
            logger.error(f"Error running validation: {e}")
            return False

        finally:
            try:
                with open(self.full_file_path, 'w') as f:
                    f.write(self.initial_content)
                logger.info(f"Original content restored to {self.full_file_path}.")
            except Exception as e:
                logger.error(f"Error restoring original content to {self.full_file_path}: {e}")



        
    def main(self):
        try: 
            self.stats['start_time'] = time.time()
            if not openai.api_key: 
                logger.warning("OPENAI_API_KEY is not set. Skipping patch generation.") 
                return
            try:
                with open(self.json_file_path, 'r') as f:
                    self.warnings = json.load(f)
                    self.stats['total_issues'] = len(self.warnings)
            except Exception as e:
                logger.error(f"Error reading warnings JSON: {e}")
                return

            logger.info("Patch Generation Started...")
            start_time = time.time()


            for warning in self.warnings:
                logger.info(f"Processing warning ID {warning['id']}...")
                try:
                    self.process_warning(warning)
                except KeyboardInterrupt:
                    logger.warning("Keyboard interrupt detected. Stopping the script gracefully.")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error processing warning ID {warning['id']}: {e}")
                    continue
                logger.info(f"Finished processing warning ID {warning['id']}.")


            try:
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.warnings, f, indent=4)
            except Exception as e:
                logger.error(f"Error saving updated issues JSON: {e}")

            elapsed_time = time.time() - start_time
            logger.info(f"Patch generation completed in {elapsed_time:.2f} seconds")
            self.visualizer.update_metrics(self.model_name, {
                'total_issues': self.stats['total_issues'],
                'build_failures': self.compilation_or_test_errors,
                'validation_failures': self.validation_errors,
                'successful_patches': self.successful_patches,
                'non_applicabale_diffs': self.non_applicabale_diffs,
                'warnings_dict': self.warnings_dict,
                'total_attempts': self.stats['total_attempts'],
                'prompt_tokens': int(statistics.mean(self.input_tokens)) if self.input_tokens else 0,
                'response_tokens': int(statistics.mean(self.response_tokens)) if self.response_tokens else 0,
                'original_warnings_dict': self.mutable_warnings,
                'elapsed_time': elapsed_time
            })
            os.makedirs(self.visualize_path, exist_ok=True)
            self.visualizer.generate_comparison_charts(self.visualize_path)
            self.visualizer.save_metrics(os.path.join(self.visualize_path, f'benchmark_metrics_round_{self.num_of_rounds}.json'))
            logger.info(f"Benchmarking results saved to {self.visualize_path}")
        except KeyboardInterrupt:
            logger.error("Keyboard interrupt detected. Stopping the script gracefully.")
            return
        finally:
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
                        model=self.model_name,
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


    def call_llama3_with_retries(self, prompt, max_retries=3):
        try:
            retries = 0
            while retries < max_retries:
                try:
                    time.sleep(2)
                    response = self.client2.chat.completions.create(
                        model="llama-3.2-90b-text-preview",
                        # model="llama-3.1-70b-versatile",

                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that can fix code issues, please return the output as one single code block extension ```patch```."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    return response
                except Exception as e:
                    print(f"Unexpected error with llama3.2: {e}")
                    retries+=1
                    break
        except Exception as e:
            return None
        

    def update_json_with_diff(self, json_content, diff_content):
        lines_dict = json.loads(json_content)
        empty_lines = {key: value.strip() for key, value in lines_dict.items() if value.strip() == ""}
        updated_diff_lines = []
        diff_lines = diff_content.splitlines()
        target = -1
        added_empty_lines = set()

        for line in diff_lines:
            updated_diff_lines.append(line)


            for key in empty_lines.keys():

                previous_line = lines_dict.get(f"Line:{int(key.split(':')[1]) - 1}", "").strip()
                next_line = lines_dict.get(f"Line:{int(key.split(':')[1]) + 1}", "").strip()

                if line.startswith('-') and previous_line == line.replace('-', '').strip():
                    target = len(updated_diff_lines)


                if target != -1 and line.startswith('-') and next_line == line.replace('-', '').strip():
                    if key not in added_empty_lines:
                        updated_diff_lines.insert(target, "- ")
                        added_empty_lines.add(key)
                        target = -1

        return "\n".join(updated_diff_lines)