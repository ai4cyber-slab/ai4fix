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
import shutil
import tempfile
import multiprocessing
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import copy

from utils.logger import logger
from utils.findMethod import get_method_info_if_any
from sast.sast_orchestrator import SASTOrchestrator
from config.llm_configuration import llm_response
from patch_generation.mesure import BenchmarkVisualizer
from symbolic_execution.execution import SymbolicExecution
from patch_generation.warnings_mapping import ALL_WARNINGS


def extract_json_section_from_code(code_content, start_line, end_line):
    lines = code_content.split('\n')
    extracted_lines = {}
    for i in range(start_line - 1, end_line):
        if i < 0 or i >= len(lines):
            continue
        line = lines[i].rstrip() if lines[i].strip() else ''
        extracted_lines[f"Line:{i + 1}"] = line
    return json.dumps(extracted_lines, indent=2)


def extract_patch_from_response_worker(response_text):
    content_blocks = re.findall(r'```(?:[^\s]*)?\s*(.*?)\s*```', response_text, re.DOTALL)
    return "\n".join(content_blocks).strip() if content_blocks else response_text.strip()


def update_java_file_worker(java_file_path, initial_json, updated_json):
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


def run_tests_worker(build_tool, cwd, env):
    try:
        if build_tool.lower() == 'maven':
            command = ['mvn', 'clean', 'test', '-Dmaven.compiler.incremental=true', '-T', str(4)]
        elif build_tool.lower() == 'gradle':
            command = ['gradle', 'clean', 'test', '--no-daemon', '--parallel', f'-Dorg.gradle.workers.max={4}']
        elif build_tool.lower() == 'javac':
            java_files = [str(file) for file in Path(cwd, 'src', 'main', 'java').rglob('*.java')]
            if java_files:
                command = ['javac', '-d', os.path.join(cwd, 'build', 'classes', 'main', 'java')] + java_files
            else:
                raise ValueError("No Java files found to compile.")
        else:
            raise ValueError(f"Unsupported build tool: {build_tool}")

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env
        )
        return result
    except Exception as e:
        logger.error(f"Error running tests with {build_tool}: {e}")
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=str(e))


def analyze_build_output_worker(build_tool, result):
    error_detected = False
    try:
        if build_tool.lower() == 'maven':
            error_keywords = ["BUILD FAILURE", "[ERROR] COMPILATION ERROR :"]
        elif build_tool.lower() == 'gradle':
            error_keywords = ["BUILD FAILED", "Compilation failed"]
        elif build_tool.lower() == 'javac':
            error_keywords = ["error:"]
        else:
            raise ValueError(f"Unsupported build tool: {build_tool}")

        output_to_analyze = result.stderr if build_tool.lower() == 'javac' else result.stdout
        for line in output_to_analyze.split("\n"):
            if any(keyword in line for keyword in error_keywords):
                error_detected = True
                break
    except Exception as e:
        logger.error(f"Error analyzing build output: {e}")
        error_detected = True

    return error_detected


def tools_validation_worker(name, tag, sast, symbolic, mutable_warnings):
    logger.info(f"Running validation for {name} with tag '{tag}' ...")
    try:
        if tag == "SE":
            logger.info("Using symbolic execution tool for validation.")
            after = symbolic.analyze(validation=True)
        elif tag == "SB":
            logger.info("Using SpotBugs tool for validation.")
            after = sast.run_all(validation=True, tool="SB")
        elif tag == "PMD":
            logger.info("Using PMD tool for validation.")
            after = sast.run_all(validation=True, tool="PMD")
        else:
            logger.info("Using all SAST tools for validation.")
            after = sast.run_all(validation=True)

        before = mutable_warnings.copy()

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


def call_ai_with_retries_worker(provider, model, api_key, prompt, max_retries=3):
    try:
        retries = 0
        while retries < max_retries:
            try:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant that can fix code issues and returns only a json block and no further explanation."},
                    {"role": "user", "content": prompt},
                ]
                response = llm_response(provider, model, api_key, messages)
                return response
            except Exception as e:
                logger.error(f"Unexpected error: {e}, retrying...")
            retries += 1
            time.sleep(2 ** retries + random.uniform(0, 1))
    except Exception as e:
        logger.error(f"AI call failed after retries: {e}")
    return None


def code_file_to_json(java_file_path):
    with open(java_file_path, 'r') as java_file:
        lines = java_file.readlines()
    lines_dict = {"Line:"+str(i + 1): line.rstrip() if line.strip() else '' for i, line in enumerate(lines)}
    json_output = json.dumps(lines_dict, indent=2)
    return json_output

def extracted_section(json_output, start_key, end_key):
    lines_dict = json.loads(json_output)
    start_index = list(lines_dict.keys()).index(start_key)
    end_index = list(lines_dict.keys()).index(end_key)
    extracted_dict = dict(list(lines_dict.items())[start_index:end_index + 1])
    extracted_json = json.dumps(extracted_dict, indent=2)
    return extracted_json

def process_warning_worker(args):
    (
        warning,
        config,
        warning_dict,
        model_name,
        provider,
        api_key,
        build_tool,
        base_project_path,
        diffs_output_dir,
        json_file_path
    ) = args

    # Local stats for this warning
    local_stats = {
        'warning_id': warning['id'],
        'passed': False,
        'validation_passed': True,
        'mvn_test_passed': True,
        'applicable_patch': True,
        'non_applicabale_diffs': 0,
        'validation_errors': 0,
        'compilation_or_test_errors': 0,
        'successful_patches': 0,
        'total_attempts': 0,
        'diff_file_name': None,
        'diff_file_path': None,
        'explanation': warning['explanation'],
        'input_tokens': [],
        'response_tokens': []
    }

    try:
        # Create a unique temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"patch_{warning['id']}_")
        process_project_directory_core = temp_dir
        temp_dir_for_maven = tempfile.mkdtemp(prefix=f"patch_{warning['id']}")

        # Copy the project to the temporary directory
        shutil.copytree(base_project_path, temp_dir, dirs_exist_ok=True)

        # Update environment variables
        env = os.environ.copy()
        env["MAVEN_OPTS"] = "-Xms512m -Xmx2048m"
        env["MAVEN_OPTS"] += f" -Djava.io.tmpdir={temp_dir_for_maven}"
        env["TMPDIR"] = temp_dir_for_maven
        env["TEMP"] = temp_dir_for_maven
        env["TMP"] = temp_dir_for_maven

        # Initialize necessary components
        sast = SASTOrchestrator(config)
        symbolic = SymbolicExecution(config)
        mutable_warnings = warning_dict.copy()

        # Extract warning details
        explanation = warning['explanation']
        items = warning['items']
        name = warning['name']
        tag = warning['tags']

        for item in items:
            textrange = item['textrange']
            file_path = textrange['file']
            startLine = textrange['startLine']
            endLine = textrange['endLine']
            

            full_file_path = os.path.join(temp_dir, file_path)
            code_in_json_format = code_file_to_json(full_file_path)
            initial_content = ""
            try:
                with open(full_file_path, 'r') as f:
                    file_content = f.readlines()
                    initial_content = ''.join(file_content)
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
                extract_json_section = extracted_section(code_in_json_format, f"Line:{adjusted_start_line}", f"Line:{adjusted_end_line}")
            else:
                extract_json_section = extracted_section(code_in_json_format, f"Line:{startLine}", f"Line:{endLine}")

            if METHOD_START and METHOD_END:
                extract_json_section = extracted_section(code_in_json_format, f"Line:{METHOD_START}", f"Line:{METHOD_END}")

            while attempt < max_attempts:
                attempt += 1
                local_stats['total_attempts'] += 1
                logger.info(f"Process {os.getpid()} - Attempt {attempt} for warning ID {warning['id']}...")

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
                    {json.dumps(input_example, indent=2)}
                    ```

                    Updated JSON:
                    ```json
                    {json.dumps(ouput_example, indent=2)}
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
                    Provide the output in same format and only that no further explanation is needed.
                    """
                
                os.makedirs(diffs_output_dir, exist_ok=True)

                # Call AI with retries
                response = call_ai_with_retries_worker(provider, model_name, api_key, prompt)
                if response is None:
                    logger.error(f"Failed to get AI response for warning ID {warning['id']} on attempt {attempt}.")
                    continue

                generated_patch = extract_patch_from_response_worker(response['message'])
                previous_generated_patch = generated_patch

                # Apply the patch
                update_success = update_java_file_worker(full_file_path, extract_json_section, generated_patch)
                if not update_success:
                    local_stats['applicable_patch'] = False
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                    except Exception as e:
                        logger.error(f"Error while restoring original content to {full_file_path}: {e}")
                    continue
                else:
                    patch_applied = True
                    local_stats['passed'] = True

                # Run tests
                logger.info(f"Process {os.getpid()} - Running '{build_tool} test' for warning ID {warning['id']}...")
                result = run_tests_worker(build_tool, process_project_directory_core, env)
                error_detected = analyze_build_output_worker(build_tool, result)

                if error_detected:
                    local_stats['applicable_patch'] = True
                    local_stats['validation_passed'] = True
                    local_stats['mvn_test_passed'] = False
                    logger.warning(f"Process {os.getpid()} - {build_tool} tests failed for warning ID {warning['id']}. Retrying...")
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Process {os.getpid()} - Reverted {full_file_path} to its initial content due to {build_tool} test failure.")
                    except Exception as e:
                        logger.error(f"Process {os.getpid()} - Error restoring original content to {full_file_path}: {e}")
                    continue
                else:
                    local_stats['mvn_test_passed'] = True
                    logger.info(f"Process {os.getpid()} - {build_tool} tests passed for warning ID {warning['id']}.")

                # Run validation
                local_config = copy.deepcopy(config)
                local_config.set('DEFAULT', 'config.project_root', temp_dir)
                sast = SASTOrchestrator(local_config)
                symbolic = SymbolicExecution(local_config)
                validation_passed = tools_validation_worker(name, tag, sast, symbolic, mutable_warnings)
                

                if validation_passed:
                    local_stats['mvn_test_passed'] = True
                    local_stats['applicable_patch'] = True
                    local_stats['validation_passed'] = True
                    local_stats['was_fixed'] = True
                    local_stats['input_tokens'].append(response['input_tokens'])
                    local_stats['response_tokens'].append(response['output_tokens'])


                    try:
                        with open(full_file_path, 'r') as f:
                            new_file_content = f.readlines()
                            updated_content = ''.join(new_file_content)
                    except Exception as e:
                        logger.error(f"Process {os.getpid()} - Error reading file {full_file_path}: {e}")
                        continue

                    diff = difflib.unified_diff(
                        initial_content.splitlines(keepends=True),
                        updated_content.splitlines(keepends=True),
                        fromfile=file_path,
                        tofile=file_path,
                        n=2
                    )
                    diff_text = ''.join(diff)

                    diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}_attempt_{attempt}.diff"
                    diff_file_path = os.path.join(diffs_output_dir, diff_file_name)
                    try:
                        with open(diff_file_path, 'w') as diff_file:
                            diff_file.write(diff_text)
                        local_stats['diff_file_name'] = diff_file_name
                        local_stats['diff_file_path'] = diff_file_path
                    except Exception as e:
                        logger.error(f"Process {os.getpid()} - Error writing diff to file {diff_file_path}: {e}")

                    
                    break
                else:
                    local_stats['applicable_patch'] = True
                    local_stats['validation_passed'] = False
                    local_stats['mvn_test_passed'] = True
                    local_stats['was_fixed'] = False
                    try:
                        with open(full_file_path, 'w') as f:
                            f.write(initial_content)
                            logger.info(f"Process {os.getpid()} - Reverted {full_file_path} to its initial content due to validation failure.")
                    except Exception as e:
                        logger.error(f"Process {os.getpid()} - Error restoring original content to {full_file_path}: {e}")

                    if attempt >= max_attempts:
                        logger.warning(f"Process {os.getpid()} - Maximum attempts reached for warning ID {warning['id']}.")
                    else:
                        logger.info(f"Process {os.getpid()} - Retrying for warning ID {warning['id']}...")
    except Exception as e:
        logger.error(f"Process {os.getpid()} - Unexpected error processing warning ID {warning['id']}: {e}")
    finally:
        shutil.rmtree(temp_dir)
        logger.info(f"Removed temporary directory: {temp_dir}")

        shutil.rmtree(temp_dir_for_maven)
        logger.info(f"Removed process project directory: {temp_dir_for_maven}")
    return local_stats


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
        self.cores_to_use = self.config.get('DEFAULT', 'config.parallel_workers', fallback='1')
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

    def save_warnings_json(self):
        """Save the updated warnings JSON file."""
        try:
            with open(self.json_file_path, 'w') as f:
                json.dump(self.warnings, f, indent=4)
                logger.info(f"Saved updated warnings JSON to {self.json_file_path}")
        except Exception as e:
            logger.error(f"Error saving updated warnings JSON: {e}")

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
                'prompt_tokens': int(statistics.mean(self.input_tokens)) if self.input_tokens and statistics.mean(self.input_tokens) is not None else 0,
                'response_tokens': int(statistics.mean(self.response_tokens)) if self.response_tokens and statistics.mean(self.response_tokens) is not None else 0,
                'original_warnings_dict': self.mutable_warnings,
                'elapsed_time': elapsed_time
            })
            os.makedirs(self.visualize_path, exist_ok=True)
            self.visualizer.generate_comparison_charts(self.visualize_path)
            self.visualizer.save_metrics(os.path.join(self.visualize_path, f'benchmark_metrics_round_{self.num_of_rounds}.json'))
            logger.info(f"Benchmarking results saved to {self.visualize_path}")
        except Exception as e:
            logger.warning("Interruption during visualization and metrics generation.")
            logger.info("Saving the visualization and metrics ...")

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
            logger.info(f"Total warnings to process: {total_warnings}")

            # Prepare arguments for multiprocessing
            args_list = []
            for warning in self.warnings:
                args = (
                    warning,
                    self.config,
                    self.warnings_dict,
                    self.model_name,
                    self.provider,
                    self.api_key,
                    self.build_tool,
                    self.base_dir,
                    self.diffs_output_dir,
                    self.json_file_path
                )
                args_list.append(args)

            # Determine number of worker processes
            num_workers = min(len(args_list), int(self.cores_to_use))
            logger.info(f"Starting multiprocessing with {num_workers} workers...")

            with multiprocessing.Pool(processes=num_workers) as pool:
                results = pool.map(process_warning_worker, args_list)

            # Process results
            for res in results:
                name = None
                for warning in self.warnings:
                    if warning['id'] == res.get('warning_id'):
                        name = warning['name']
                        break
                if res.get('was_fixed', False) and name in self.warnings_dict:
                    self.warnings_dict[name] -= 1
                # Aggregate statistics from workers
                self.stats['total_attempts'] += res.get('total_attempts', 0)
                if res.get('passed', False):
                    self.successful_patches += 1
                if not res.get('validation_passed', True):
                    self.validation_errors += 1
                if not res.get('mvn_test_passed', True):
                    self.compilation_or_test_errors += 1
                if not res.get('applicable_patch', True):
                    self.non_applicabale_diffs += 1

                # Merge token usage data
                if 'input_tokens' in res and res['input_tokens']:
                    self.input_tokens.extend(res['input_tokens'])
                if 'response_tokens' in res and res['response_tokens']:
                    self.response_tokens.extend(res['response_tokens'])
                """ if name and name in self.warnings_dict:
                    self.warnings_dict[name] -= 1 """

                # Update JSON file with patch information
                for warning in self.warnings:
                    if warning['id'] == res.get('warning_id'):
                        for item in warning['items']:
                            if 'patches' not in item:
                                item['patches'] = []
                            explanation = res.get('explanation', '')
                            if res.get('diff_file_name') and res.get('diff_file_path'):
                                item['patches'].append({
                                    "path": res['diff_file_name'],
                                    "explanation": explanation
                                })
                        break

            # Save updated warnings JSON
            self.save_warnings_json()


        except KeyboardInterrupt:
            logger.error("Keyboard interrupt detected in main. Saving progress and stopping the script gracefully.")
            self.save_warnings_json()
            raise

        finally:
            elapsed_time = time.time() - self.start_time
            self.stats['elapsed_time'] = elapsed_time
            logger.info(f"Patch generation completed in {elapsed_time:.2f} seconds")
            try:
                self.generate_visualizations_and_metrics(elapsed_time)
            except Exception as e:
                logger.error(f"Error generating visualizations and metrics: {e}")