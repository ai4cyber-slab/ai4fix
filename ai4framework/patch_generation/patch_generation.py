import os
import re
import sys
import time
import json
import random
import statistics
import subprocess
import commentjson as cjson
import difflib

from dotenv import load_dotenv, find_dotenv
from utils.logger import logger
from utils.findMethod import get_method_info_if_any
from sast.sast_orchestrator import SASTOrchestrator
from config.llm_configuration import llm_response
from patch_generation.mesure import BenchmarkVisualizer
from symbolic_execution.execution import SymbolicExecution
from patch_generation.warnings_mapping import ALL_WARNINGS

class PatchGenerator:
    def __init__(self, config, warning_dict, num_of_rounds):
        """Initialize PatchGenerator with configuration."""
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        self.config = config
        self.provider = self.config.get('API', 'config.provider').lower()
        self.model = self.config.get('API', 'config.model')
        self.api_key = self.config.get('API', 'config.key', fallback='').strip()
        self.build_tool = self.config.get('DEFAULT', 'config.build_tool', fallback='maven').lower()
        if self.api_key == '':
            logger.warning("API key not found. Please set it in the configuration.")
            sys.exit(1)

        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.sast = SASTOrchestrator(self.config)
        self.symbolic = SymbolicExecution(self.config)
        self.visualize_path = os.path.join(self.project_path, '.ai4framework', 'visualizations')
        self.base_dir = self.project_path
        self.diffs_output_dir = self.config.get('DEFAULT', 'config.results_path')
        self.json_file_path = self.config.get('DEFAULT', 'config.issues_path')
        self.model_name = self.config.get("API", "config.model")
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
        self.start_time = time.time()


        self.warnings_dict = warning_dict
        self.mutable_warnings = warning_dict.copy()

    def run_tests(self, build_tool):
        """
        Run the test command using the specified build tool (Maven or Gradle) and return the result.

        Args:
            build_tool (str): The build tool to use ('maven' or 'gradle').

        Returns:
            subprocess.CompletedProcess: The result of the test execution.
        """
        try:
            if build_tool.lower() == 'maven':
                command = ['mvn', 'test', '-Dmaven.compiler.incremental=true', '-T', str(os.cpu_count())]
            elif build_tool.lower() == 'gradle':
                command = ['gradle', 'test', '--no-daemon', '--parallel', f'-Dorg.gradle.workers.max={os.cpu_count()}']
            else:
                raise ValueError(f"Unsupported build tool: {build_tool}")

            with subprocess.Popen(
                command,
                cwd=self.project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ) as process:
                stdout, stderr = process.communicate()
                result = subprocess.CompletedProcess(
                    args=command, 
                    returncode=process.returncode, 
                    stdout=stdout, 
                    stderr=stderr
                )

            return result

        except Exception as e:
            logger.error(f"An error occurred while running tests with {build_tool}: {str(e)}")
            raise


    def analyze_build_output(self, build_tool, result):
        """
        Analyze the build tool output to detect and categorize errors.

        Args:
            build_tool (str): The build tool used ('maven' or 'gradle').
            result (CompletedProcess): The result object containing the build output.

        Returns:
            bool: True if an error is detected, False otherwise.
        """
        error_detected = False

        if build_tool.lower() == 'maven':
            error_keywords = ["BUILD FAILURE", "[ERROR] COMPILATION ERROR :"]
        elif build_tool.lower() == 'gradle':
            error_keywords = ["BUILD FAILED", "Compilation failed"]
        else:
            raise ValueError(f"Unsupported build tool: {build_tool}")

        for line in result.stdout.split("\n"):
            if any(keyword in line for keyword in error_keywords):
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

    def update_java_file(self, java_file_path, initial_json, updated_json):
        """
        Updates the Java file based on the initial JSON and the updated JSON,
        filling missing lines with empty content only for lines between the first and last line of the initial JSON.

        :param java_file_path: Path to the Java file to modify.
        :param initial_json: Initial JSON string with lines to be updated.
        :param updated_json: Updated JSON string with new or modified lines.
        :return: True if the update is successful, False otherwise.
        """
        try:
            if isinstance(initial_json, str):
                initial_json = cjson.loads(initial_json)
            if isinstance(updated_json, str):
                updated_json = cjson.loads(updated_json)

            initial_lines_set = {int(key.split(":")[1]) for key in initial_json.keys()}
            min_initial_line = min(initial_lines_set)
            max_initial_line = max(initial_lines_set)
            updated_lines = {int(key.split(":")[1]): value for key, value in updated_json.items()}
            
            for line_number in range(min_initial_line, max_initial_line + 1):
                if line_number not in updated_lines:
                    updated_lines[line_number] = ""

            with open(java_file_path, 'r') as file:
                lines = file.readlines()

            with open(java_file_path, 'w') as file:
                new_lines = lines.copy()
                lines_inserted = 0
                for line_number in sorted(updated_lines.keys()):
                    content = updated_lines[line_number]

                    if line_number <= max_initial_line:
                        if 1 <= line_number <= len(new_lines):
                            new_lines[line_number - 1] = (content + '\n') if content else '\n'
                        else:
                            raise IndexError(f"Line number {line_number} is out of range for the file.")
                    else:
                        insert_position = max_initial_line + lines_inserted
                        new_lines.insert(insert_position, (content + '\n') if content else '\n')
                        lines_inserted += 1
                file.writelines(new_lines)
            return True
        except Exception as e:
            return False
    

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
            self.applicable_patch = True
            self.validation_passed = True
            self.mvn_test_passed = True
            
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
            SOLVE_COMMAND = ALL_WARNINGS.get(name, explanation)
            METHOD_INFO, METHOD_START, METHOD_END = get_method_info_if_any(code_in_json_format, startLine, endLine)
            adjusted_start_line = int(startLine) - 5
            adjusted_end_line = int(endLine) + 5
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
                    input_example = {
                        "Line:34": "public void exampleMethod() {",
                        "Line:35": "    System.out.println(\"Hello, World!\");",
                        "Line:36": "}"
                    }
                    ouput_example = {
                        "Line:34": "public void exampleMethod() {",
                        "Line:35": "    System.out.println(\"Updated Message!\");",
                        "Line:36": "}"
                    }
                    prompt = f"""
                    You are a GPT that generates programmatic solutions to fix Java code issues. Your task is to modify the provided JSON content to resolve the issue. Follow these guidelines:

                    1. **Objective**:
                    - Update the provided JSON content to fix the issue as specified in the problem description.

                    2. **Modification Rules**:
                    - Replace any incorrect or problematic lines in the JSON content with the corrected lines.
                    - If necessary, remove redundant lines or add new lines to ensure the solution is valid and complete.
                    - Ensure the updated JSON contains all required lines and remains syntactically valid Java code.

                    3. **Output Requirements**:
                    - Return the full modified JSON content, structured similarly to the input JSON.
                    - Preserve the format of the original JSON, including keys like `Line:<line_number>` and their corresponding values.

                    4. **Validation**:
                    - Ensure the updated JSON represents valid, compilable Java code.
                    - Avoid redundant or conflicting changes.
                    - If no valid solution is possible, respond with `"I DO NOT KNOW"`.

                    5. **Input Context**:
                    - Use the provided JSON snippet as the basis for your solution update it entirely:
                        ```json
                        {extract_json_section}
                        ```

                    6. **Example**:
                    Input JSON:
                    ```json
                    {input_example}
                    ```

                    Updated JSON:
                    ```json
                    {ouput_example}
                    ```

                    7. **Change Request**:
                    - Fix the static analysis tool warning: `{explanation}` as follows {SOLVE_COMMAND}:
                        - The issue starts at line {startLine} and ends at line {endLine}.
                        - Solve the issue by performing the required changes to the JSON content directly.
                    - If no valid solution is possible, respond with `"I DO NOT KNOW"`.
                    """
                else:
                    prompt = f"""
                    The previous attempt to fix the issue did not resolve it.
                    Here is the strategy you gave me in last attempt:
                    {previous_generated_patch}
                    Explanation of the issue: {explanation}
                    the issue is between line {startLine} and line {endLine}
                    Here is the full original file code in json format with lines as the keys use them when providing the strategy accurately:
                    {extract_json_section}
                    Instructions:
                    Analyze the previous attempt and identify why it did result in incorrect java code.
                    Solve it by: {SOLVE_COMMAND}
                    Provide the output in same format and only that no further explination is needed.
                    """
                    
                os.makedirs(self.diffs_output_dir, exist_ok=True)

                response = self.call_ai_with_retries(prompt)
                if response is None:
                    logger.error(f"Failed to get response.")
                    break
                
                generated_patch = self.extract_patch_from_response(response['message'])
                previous_generated_patch = generated_patch
                try:
                    if not self.update_java_file(self.full_file_path, extract_json_section , generated_patch):
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


                logger.info(f"Running '{self.build_tool} test' for warning ID {warning['id']}...")
                if self.build_tool in ['maven', 'gradle']:
                    result = self.run_tests(self.build_tool)
                    error_detected = self.analyze_build_output(self.build_tool, result)
                else:
                    raise ValueError(f"Unsupported build tool: {self.build_tool}")
                
                if error_detected:
                    self.applicable_patch = True
                    self.validation_passed = True
                    self.mvn_test_passed = False
                    logger.warning(f"{self.build_tool} tests failed. Retrying...")
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Reverted {full_file_path} to its initial content due to Maven test failure.")
                    except Exception as e:
                        logger.error(f"Error restoring original content to {full_file_path}: {e}")
                    continue

                logger.info(f"{self.build_tool} tests passed.")
                
                self.validation_passed = self.tools_validation(name, tag)
                if self.validation_passed:
                    self.applicable_patch = True
                    self.validation_passed = True
                    self.mvn_test_passed = True
                    self.input_tokens.append(response['input_tokens'])
                    self.response_tokens.append(response['output_tokens'])

                    try:
                        with open(full_file_path, 'r') as f:
                            new_file_content = f.readlines()
                            updated_content = ''.join(new_file_content)
                    except Exception as e:
                        logger.error(f"Error reading file {full_file_path}: {e}")
                        continue

                    diff = difflib.unified_diff(
                        self.initial_content.splitlines(keepends=True),
                        updated_content.splitlines(keepends=True),
                        fromfile=file_path,
                        tofile=file_path,
                        n=2
                    )
                    diff_text = ''.join(diff)

                    diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}_attempt_{attempt}.diff"
                    diff_file_path = os.path.join(self.diffs_output_dir, diff_file_name)
                    try:
                        with open(diff_file_path, 'w') as diff_file:
                            diff_file.write(diff_text)
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

    def main(self):
        try:
            self.stats['start_time'] = time.time()
            if self.api_key == '':
                logger.warning("API key is not set. Skipping patch generation.")
                return
            try:
                with open(self.json_file_path, 'r') as f:
                    self.warnings = json.load(f)
                    self.stats['total_issues'] = len(self.warnings)
            except Exception as e:
                logger.error(f"Error reading warnings JSON: {e}")
                return

            logger.info("Patch Generation Started...")
            self.start_time = time.time()

            total_warnings = len(self.warnings)
            for idx, warning in enumerate(self.warnings, start=1):
                logger.info(f"Processing warning ID {warning['id']}...")

                try:
                    print(f"PROGRESS UPDATE: {idx}/{total_warnings}", flush=True)
                    self.process_warning(warning)
                except KeyboardInterrupt:
                    logger.warning("Keyboard interrupt detected. Saving progress and stopping the script gracefully.")
                    self.save_warnings_json()
                    raise
                except Exception as e:
                    logger.error(f"Unexpected error processing warning ID {warning['id']}: {e}")
                    continue
                logger.info(f"Finished processing warning ID {warning['id']}.")
                self.save_warnings_json()


        except KeyboardInterrupt:
            logger.error("Keyboard interrupt detected in main. Saving progress and stopping the script gracefully.")
            self.save_warnings_json()
            raise

        finally:
            elapsed_time = time.time() - self.start_time
            logger.info(f"Patch generation completed in {elapsed_time:.2f} seconds")
            try:
                self.generate_visualizations_and_metrics(elapsed_time)
            except Exception as e:
                logger.error(f"Error generating visualizations and metrics: {e}")
            if hasattr(self, 'full_file_path') and hasattr(self, 'initial_content'):
                try:
                    logger.info(f"Restoring original content to {self.full_file_path}.")
                    with open(self.full_file_path, 'w') as f:
                        f.write(self.initial_content)
                except Exception as e:
                    logger.error(f"Error restoring original content to {self.full_file_path}: {e}")

    def save_warnings_json(self):
        """Save the updated warnings JSON file."""
        try:
            with open(self.json_file_path, 'w') as f:
                json.dump(self.warnings, f, indent=4)
                logger.info(f"Saved updated warnings JSON to {self.json_file_path}")
        except Exception as e:
            logger.error(f"Error saving updated warnings JSON: {e}")

        
    def call_ai_with_retries(self, prompt, max_retries=3):
        try:
            """Call API with retry logic and handle keyboard interrupt."""
            retries = 0
            while retries < max_retries:
                try:
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant that can fix code issues and returns only a json block and no further explination."},
                        {"role": "user", "content": prompt},
                    ]
                    response = llm_response(self.provider, self.model, self.api_key, messages)
                    return response
                except Exception as e:
                    logger.error(f"Unexpected error: {e}, retrying...")
                retries += 1
                time.sleep(2 ** retries + random.uniform(0, 1))
        except Exception as e:
            return None
    
    def generate_visualizations_and_metrics(self, elapsed_time):
        """Generate visualizations and save metrics."""
        try:
            self.visualizer.update_metrics(self.model_name, {
                'total_issues': self.stats['total_issues'],
                'build_failures': self.compilation_or_test_errors,
                'validation_failures': self.validation_errors,
                'successful_patches': self.successful_patches,
                'non_applicabale_diffs': self.non_applicabale_diffs,
                'warnings_dict': self.warnings_dict,
                'total_attempts': self.stats['total_attempts'],
                'prompt_tokens': int(statistics.mean(self.input_tokens)) if self.input_tokens and statistics.mean(self.input_tokens) != None else 0,
                'response_tokens': int(statistics.mean(self.response_tokens)) if self.response_tokens and statistics.mean(self.response_tokens) != None else 0,
                'original_warnings_dict': self.mutable_warnings,
                'elapsed_time': elapsed_time
            })
            os.makedirs(self.visualize_path, exist_ok=True)
            self.visualizer.generate_comparison_charts(self.visualize_path)
            self.visualizer.save_metrics(os.path.join(self.visualize_path, f'benchmark_metrics_round_{self.num_of_rounds}.json'))
            logger.info(f"Benchmarking results saved to {self.visualize_path}")
        except Exception as e:
            logger.warning(f"Interruption during visualization and metrics generation.")
            logger.info(f"saving the visualization and metrics ...")