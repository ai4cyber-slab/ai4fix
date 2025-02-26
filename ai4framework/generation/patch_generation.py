import ast
from collections import defaultdict
import fcntl
import os
import re
import sys
import time
import json
import random
import statistics
import subprocess
from config.common_config import ConfigManager
import commentjson as cjson
import difflib
import shutil
import tempfile
import multiprocessing
from tabulate import tabulate
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import copy

from utils.logger import logger
from utils.findMethod import get_method_info_if_any
from sast.sast_orchestrator import SASTOrchestrator
from config.llm_configuration import llm_response
from generation.mesure import BenchmarkVisualizer
from symbolic_execution.execution import SymbolicExecution
from generation.warnings_mapping import ALL_WARNINGS
from generation.test_generation import TestGenerator
from utils.switcher import switch_java_version








####################################
# Helper functions
####################################

def parse_build_output(build_tool, result_output):
    """
    Parse the build output depending on the build tool.
    For Maven, we check for 'COMPILATION ERROR' and 'BUILD SUCCESS'.
    For other build tools (e.g., Gradle) we can add similar logic in the future.
    """
    details = {
        'compilation_error': False,
        'compilation_error_files': [],
        'failure_details': [],
        'error_details': [],
        'build_success': True,
        'mvn_test_passed' : True,
        'reason': ""
    }
    error_message = ""

    if build_tool == 'maven':
        failure_details = re.findall(r'\[ERROR\]\s+Failures:\s+(.*?):(\d+)\s+(.*)', result_output)
        error_details = re.findall(r'\[ERROR\]\s+Errors:\s+(.*?):(\d+)\s+(.*)', result_output)

        details['failure_details'] = failure_details
        details['error_details'] = error_details
        line_counter=0
        for line in result_output.split("\n"):
            if "[ERROR]" in line:
                line_counter += 1
                if "cannot" in line:
                    if line_counter == 2:
                        split_line = line.split("] ")
                        if len(split_line) > 2:
                            error_message_key = split_line[2]
                            error_message = error_message_key
                        else:
                            error_message = line
                        
                        lines = result_output.split("\n")
                        next_line_index = lines.index(line) + 1
                        if next_line_index < len(lines):
                            next_line = lines[next_line_index]
                            error_message += " " + next_line
                        break
                else:
                    if line_counter == 2:
                        split_line = line.split("] ")
                        if len(split_line) > 2:
                            error_message = split_line[2]
                        else:
                            error_message = line
                        break

        if "COMPILATION ERROR" in result_output:
            details['compilation_error'] = True
            error_files = re.findall(r'\[ERROR\] (.*?\.java):', result_output)
            details['compilation_error_files'] = error_files
            details['mvn_test_passed'] = False
            details['build_success'] = False
            logger.warning(f"{build_tool} compilation failed")
            details['reason']= error_message
        elif "BUILD SUCCESS" not in result_output:
            logger.warning(f"{build_tool} build failed")
            details['reason']= error_message

        elif "BUILD SUCCESS" in result_output and "COMPILATION ERROR" not in result_output:
            details['build_success'] = True

    elif build_tool == 'gradle':
        # 1) Check for build success/failure
        if "BUILD SUCCESSFUL" in result_output:
            details['build_success'] = True
        else:
            logger.info("GRADLE TEST FAILED")

        # 2) Detect Java compilation errors
        compilation_errors = re.findall(r'(.+?\.java):(\d+):\s+error:\s+(.*)', result_output)
        if compilation_errors:

            details['compilation_error'] = True
            # We'll collect just the file paths as a unique set, ignoring duplicates
            error_files = {file_path for file_path, _, _ in compilation_errors}
            details['compilation_error_files'] = sorted(error_files)

        # 3) Detect test failures (if any)
        test_failures = re.findall(r'(.*?) > (.*?) FAILED\s*(.*)', result_output)
        # Store them in 'failure_details' as (className, testName, extraMessage)
        for class_name, test_name, extra_msg in test_failures:
            details['failure_details'].append((class_name.strip(), test_name.strip(), extra_msg.strip()))

    else:
        raise NotImplementedError(f"Build tool '{build_tool}' not supported yet.")

    return details


def extract_json_section_from_code(code_content, start_line, end_line):
    lines = code_content.split('\n')
    extracted_lines = {}
    for i in range(start_line - 1, end_line):
        if i < 0 or i >= len(lines):
            continue
        line = lines[i].rstrip() if lines[i].strip() else ''
        extracted_lines[f"Line:{i + 1}"] = line
    return json.dumps(extracted_lines, indent=2)


def validate_test_and_patch(test_file_path, result_output, build_tool, context_for_diff_file):
    """
    Validate test and patch results. 
    Uses parse_build_output to handle build_tool specific logic.
    """
    decisions = {
        'compilation_error': False,
        'compilation_error_files': [],
        'failure_details': [],
        'error_details': [],
        'test_file_exists': os.path.exists(test_file_path) if test_file_path else False,
        'reason': ""
    }

    # logger.info(f"Test file {'exists' if decisions['test_file_exists'] else 'does not exist'} at path: {test_file_path}")

    parsed = parse_build_output(build_tool, result_output)
    decisions['mvn_test_passed'] = parsed['mvn_test_passed']
    decisions['failure_details'] = parsed['failure_details']
    decisions['error_details'] = parsed['error_details']
    decisions['compilation_error'] = parsed['compilation_error']
    decisions['compilation_error_files'] = parsed['compilation_error_files']
    decisions['build_success'] = parsed['build_success']
    decisions['reason'] = parsed['reason']

    return decisions


def derive_full_import_from_path(file_path):
    relative_path = file_path.split(os.path.join('src', 'main', 'java') + os.sep, 1)[-1]
    without_ext = relative_path[:-5]
    return without_ext.replace('/', '.')


# def generate_test_file(java_file_path, updated_section, full_import, test_generator, initial_section, diff_content):
#     try:
#         test_file_path, status, original_test_content = test_generator.generate_test(
#             java_file_path=java_file_path,
#             updated_section=updated_section,
#             full_import=full_import,
#             initial_section=initial_section,
#             diff_content=diff_content
#         )
#         if status:
#             logger.info(f"Updated test file at path: {test_file_path}")
#         else:
#             logger.info(f"Created new test file at path: {test_file_path}")
#         return test_file_path, status, original_test_content
#     except Exception as e:
#         logger.error(f"Error generating test file: {e}")
#         return None, False, None


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
        logger.error(f"Error updating Java file {java_file_path}: {e}")
        return False


def run_tests_worker(build_tool, cwd, env, jdk_compiler_version, build_mode):
    switch_java_version(str(jdk_compiler_version))
    try:
        if build_tool.lower() == 'maven':
            command = ['mvn']
            if build_mode.lower() == 'offline':
                command.append('-o')
            command.extend(['clean', 'test', '-Dmaven.compiler.incremental=true'])
            if is_parallel_build_supported(build_tool):
                command.extend(['-T', str(os.cpu_count())])
        elif build_tool.lower() == 'gradle':
            command = ['gradle']
            if build_mode.lower() == 'offline':
                command.append('--offline')
            command.extend(['test', '--no-daemon'])
            if is_parallel_build_supported(build_tool):
                command.extend(['--parallel', f'-Dorg.gradle.workers.max={os.cpu_count()}'])
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
    finally:
        switch_java_version('11')


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


def call_ai_with_retries_worker(provider, model, api_key, prompt, config, max_retries=3):
    try:
        retries = 0
        while retries < max_retries:
            try:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant that can fix code issues and returns only a json block and no further explanation."},
                    {"role": "user", "content": prompt},
                ]
                response = llm_response(provider=provider, model=model, api_key=api_key, messages=messages, endpoint=config.get('API', 'config.azure_endpoint'), api_v=config.get('API', 'config.azure_api_version'))
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

def is_parallel_build_supported(build_tool):
    if build_tool == 'gradle':
        ex = 'gradle'
    elif build_tool == 'maven':
        ex = 'mvn'
    result = subprocess.run([ex, '-v'], capture_output=True, text=True)
    if result.returncode == 0:
        if build_tool == 'maven':
            version_match = re.search(r'Apache Maven (\d+\.\d+\.\d+)', result.stdout)
            if version_match:
                version = version_match.group(1)
                major_version = int(version.split('.')[0])
                return major_version >= 3
        elif build_tool == 'gradle':
            version_match = re.search(r'Gradle (\d+\.\d+)', result.stdout)
            if version_match:
                version = version_match.group(1)
                major_version = int(version.split('.')[0])
                return major_version >= 4
    return False



def run_tests_and_collect_output(build_tool, process_project_directory_core, env, jdk_compiler_version, build_mode):
    result = run_tests_worker(build_tool, process_project_directory_core, env, jdk_compiler_version, build_mode)
    output = result.stdout + result.stderr
    return output


def get_prompt(explanation, startLine, endLine, attempt, previous_generated_patch, SOLVE_COMMAND, extract_json_section):
    if attempt == 1:
        input_example = {
            "Line:34": "public void exampleMethod() {",
            "Line:35": "    System.out.println(\"Hello, World!\");",
            "Line:36": "}"
        }
        output_example = {
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
                    {json.dumps(output_example, indent=2)}
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

    return prompt


def copy_original_project_to_temp_directory(base_project_path, temp_dir):
    shutil.copytree(base_project_path, temp_dir, dirs_exist_ok=True)


def update_build_env_vars(temp_dir_for_build_tool, build_tool):
    env = os.environ.copy()

    if build_tool == 'maven':
        env["MAVEN_OPTS"] = "-Xms512m -Xmx2048m"
        env["MAVEN_OPTS"] += f" -Djava.io.tmpdir={temp_dir_for_build_tool}"

        # Also update common system temp vars
        env["TMPDIR"] = temp_dir_for_build_tool
        env["TEMP"] = temp_dir_for_build_tool
        env["TMP"] = temp_dir_for_build_tool

    elif build_tool == 'gradle':
        env["GRADLE_OPTS"] = "-Xms512m -Xmx2048m"
        env["GRADLE_OPTS"] += f" -Djava.io.tmpdir={temp_dir_for_build_tool}"

        env["TMPDIR"] = temp_dir_for_build_tool
        env["TEMP"] = temp_dir_for_build_tool
        env["TMP"] = temp_dir_for_build_tool

    return env


def remove_file_if_exists(file_path):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Removed file: {file_path}")
        except Exception as e:
            logger.error(f"Error removing file {file_path}: {e}")


def revert_test_content(context):
    test_file_path = context['test_file_path']
    original_test_content = context['original_test_content']

    if os.path.exists(test_file_path) and original_test_content is not None:
        try:
            with open(test_file_path, 'w') as f:
                f.write(original_test_content)
            logger.info(f"Reverted test content to original in {test_file_path}")
        except Exception as e:
            logger.error(f"Error restoring original test content to {test_file_path}: {e}")


def revert_patch(context):
    full_file_path = context['full_file_path']
    initial_content = context['initial_content']

    try:
        with open(full_file_path, 'w') as f:
            f.write(initial_content)
        logger.info(f"Reverted patch in {full_file_path.split('/')[-1]}")
    except Exception as e:
        logger.error(f"Error restoring original content to {full_file_path}: {e}")


def create_diff(context, extra="", err_message=""):
    full_file_path = context['full_file_path']
    initial_content = context['initial_content']
    file_path = context['file_path']
    diffs_output_dir = context['diffs_output_dir']
    warning_id = context['warning_id']
    attempt = context['attempt']

    try:
        with open(full_file_path, 'r') as f:
            new_file_content = f.read()
    except Exception as e:
        logger.error(f"Error reading file {full_file_path}: {e}")
        return None, None

    diff = difflib.unified_diff(
        initial_content.splitlines(keepends=True),
        new_file_content.splitlines(keepends=True),
        fromfile=file_path,
        tofile=file_path,
        n=2
    )
    diff_text = ''.join(diff)

    if err_message:
        diff_text = f"# {err_message}\n\n{diff_text}"

    if extra == "":
        diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning_id}_attempt_{attempt}_{str(int(time.time()))}.diff"
    else:
        diff_file_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning_id}_attempt_{attempt}_{extra.replace(':', '-')}.diff"

    os.makedirs(diffs_output_dir, exist_ok=True)
    diff_file_path = os.path.join(diffs_output_dir, diff_file_name)

    try:
        with open(diff_file_path, 'w') as diff_file:
            diff_file.write(diff_text)
        return diff_file_name, diff_file_path
    except Exception as e:
        logger.error(f"Error writing diff to {diff_file_path}: {e}")
        return None, None



def log_retry(message, context):
    attempt = context['attempt']
    max_attempts = context['max_attempts']
    warning_id = context['warning_id']

    if attempt >= max_attempts:
        logger.warning(f"Maximum attempts reached for warning ID {warning_id}.")
    else:
        logger.info(f"{message} for warning ID {warning_id}...")


def handle_test_error(context, issue_resolved):
    decisions = context['decisions']
    status = context['status']
    test_file_path = context['test_file_path']
    process_project_directory_core = context['process_project_directory_core']
    env = context['env']
    name = context['name']
    tag = context['tag']
    sast = context['sast']
    symbolic = context['symbolic']
    mutable_warnings = context['mutable_warnings']
    local_stats = context['local_stats']
    build_tool = context['build_tool']
    jdk_compiler_version = context['jdk_compiler_version']
    build_mode = context['build_mode']


    error_files = decisions['compilation_error_files']
    is_test_error = any("/test/" in ef for ef in error_files)
    if not is_test_error:
        return False
    if not status:
        remove_file_if_exists(test_file_path)
    else:
        revert_test_content(context)

    output_after_revert = run_tests_and_collect_output(build_tool, process_project_directory_core, env, jdk_compiler_version, build_mode)
    re_decisions = parse_build_output(build_tool, output_after_revert)
    decisions['mvn_test_passed'] = re_decisions['mvn_test_passed']
    decisions['build_success'] = re_decisions['build_success']
    if re_decisions['build_success'] and not re_decisions['compilation_error']:
        if issue_resolved:
            local_stats['validation_passed'] = True
            local_stats['was_fixed'] = True

            diff_file_name, diff_file_path = create_diff(context)
            if diff_file_name and diff_file_path:
                local_stats['diff_file_name'] = diff_file_name
                local_stats['diff_file_path'] = diff_file_path

            return True
        else:
            revert_patch(context)
            try:
                revert_test_content(context)
            except TypeError as e:
                if "NoneType" in str(e):
                    # logger.info("Test was not reverted.") #TODO Turn off Test
                    pass
                else:
                    raise
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
            log_retry("Retrying", context)
            return False
    else:
        revert_patch(context)
        log_retry("Build failed. Retrying with a new patch", context)
        return False


def handle_source_error(context):
    status = context['status']
    test_file_path = context['test_file_path']
    if not status:
        remove_file_if_exists(test_file_path)
    else:
        revert_test_content(context)
    revert_patch(context)
    log_retry("Retrying with a new patch", context)
    return False


def handle_build_success(context, issue_resolved):
    name = context['name']
    tag = context['tag']
    sast = context['sast']
    symbolic = context['symbolic']
    mutable_warnings = context['mutable_warnings']
    local_stats = context['local_stats']

    if issue_resolved:
        local_stats['validation_passed'] = True
        local_stats['was_fixed'] = True
        diff_file_name, diff_file_path = create_diff(context)
        if diff_file_name and diff_file_path:
            local_stats['diff_file_name'] = diff_file_name
            local_stats['diff_file_path'] = diff_file_path
        return True
    else:
        revert_patch(context)
        try:
            revert_test_content(context)
        except TypeError as e:
            if "NoneType" in str(e):
                # logger.info("Test was not reverted.") #TODO Turn off Test
                pass
            else:
                raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        log_retry("Retrying with a new patch", context)
        return False


def handle_test_failures(context, issue_resolved):
    decisions = context['decisions']
    status = context['status']
    test_file_path = context['test_file_path']
    name = context['name']
    tag = context['tag']
    sast = context['sast']
    symbolic = context['symbolic']
    mutable_warnings = context['mutable_warnings']
    jdk_compiler_version = context['jdk_compiler_version']
    build_mode = context['build_mode']
    local_stats = context['local_stats']
    process_project_directory_core = context['process_project_directory_core']
    env = context['env']
    build_tool = context['build_tool']

    target_test_class_name = None
    if context['test_file_path']:
        target_test_class_name = os.path.splitext(os.path.basename(context['test_file_path']))[0]

    failures = decisions['failure_details'] + decisions['error_details']
    our_test_failed = False
    another_test_failed = False

    for detail in failures:
        test_class, line_number, message = detail
        class_name = test_class.split("/")[-1].replace(".java", "")
        if target_test_class_name and target_test_class_name in class_name:
            our_test_failed = True
        else:
            another_test_failed = True

    if our_test_failed and not another_test_failed:
        if not status:
            remove_file_if_exists(test_file_path)
        else:
            revert_test_content(context)

        output_after_test_drop = run_tests_and_collect_output(build_tool, process_project_directory_core, env, jdk_compiler_version, build_mode)
        re_decisions = parse_build_output(build_tool, output_after_test_drop)
        if re_decisions['build_success'] and not re_decisions['compilation_error']:
            if issue_resolved:
                local_stats['validation_passed'] = True
                local_stats['was_fixed'] = True

                diff_file_name, diff_file_path = create_diff(context)
                if diff_file_name and diff_file_path:
                    local_stats['diff_file_name'] = diff_file_name
                    local_stats['diff_file_path'] = diff_file_path

                return True
            else:
                revert_patch(context)
                revert_test_content(context)
                log_retry("Retrying", context)
                return False
        else:
            revert_patch(context)
            log_retry("Retrying with a new patch", context)
            return False
    else:
        if not status:
            remove_file_if_exists(test_file_path)
        else:
            revert_test_content(context)
        revert_patch(context)
        log_retry("Retrying with a new patch", context)
        return False


def handle_compilation_error(context, issue_resolved):
    decisions = context['decisions']

    if decisions['compilation_error']:
        error_files = decisions['compilation_error_files']
        if any("/test/" in ef for ef in error_files):
            return handle_test_error(context, issue_resolved)
        else:
            return handle_source_error(context)
    return None

def remove_last_extra_closing_brace(json_str: str) -> str:
    """
    Removes the last occurrence of a line that consists only of a closing curly brace ('}')
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON input") from e
    
    # detect lines that are just '}'
    brace_only_pattern = re.compile(r'^\s*\}\s*$')

    # Identify the last line containing only a '}'
    last_brace_key = None
    for key in reversed(sorted(data.keys(), key=lambda k: int(k.split(":")[1]))):  # Sort by line number descending
        if brace_only_pattern.match(data[key]):
            last_brace_key = key
            break

    # Remove the last closing brace
    if last_brace_key:
        del data[last_brace_key]

    return json.dumps(data, indent=4)

def check_new_issues(file_path, original_file_issue_count):
    logger.debug(f"Checking for new issues in {file_path}...")
    introduced_new_issue = "False"
    new_warnings_dict = {}

    try:
        cmd = [
            "python",
            "/app/orchestrator.py",
            "--single-file", file_path,
            "--count-issues"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            logger.warning(f"Orchestrator returned non-zero exit code: {result.returncode}")
            # We can treat a non-zero exit as a possible build failure or skip.

        match_count = re.search(r"Total issue count:\s*(\d+)", result.stdout)
        if match_count:
            new_count = int(match_count.group(1))
            logger.info(
                f"Orchestrator found {new_count} issues in {file_path}; originally had {original_file_issue_count}"
            )
            # If new_count >= original_file_issue_count => we introduced new or same # issues
            if new_count >= original_file_issue_count:
                introduced_new_issue = "True"
        else:
            introduced_new_issue = "build failed"

        # Grab the dictionary after "warnings_dict_original:"
        match_dict = re.search(r"warnings_dict_original:\s*(\{.*\})", result.stdout, re.DOTALL)
        if match_dict:
            dict_str = match_dict.group(1).strip()
            try:
                new_warnings_dict = ast.literal_eval(dict_str)
            except Exception as parse_err:
                logger.error(f"Failed to parse warnings_dict_original as Python dict: {parse_err}")
        else:
            logger.warning("build failed.")

    except Exception as e:
        logger.error(f"Error checking new issues in {file_path}: {e}")

    return {
        "introduced_new_issue": introduced_new_issue,
        "new_warnings_dict": new_warnings_dict
    }

def check_new_external_issues(file_path, original_file_issue_count, temp_dir):
    """
    1. Temporarily set config.project_root to temp_dir
    2. Spawn the orchestrator with --skip-patches and --external-json, streaming its output
    3. Extract issue data for the specified file
    4. Determine if a new issue was introduced based on the counts
    5. Restore the original config.project_root after the command completes
    """
    logger.info(f"original_file_issue_count: {original_file_issue_count}")
    introduced_new_issue = "False"
    new_warnings_dict = {}

    # 1) Get the global config
    config_data = ConfigManager.get_config(commit_sha=None)

    old_project_root = config_data.get("DEFAULT", "config.project_root", fallback="")
    old_env_project_path = os.environ.get("PROJECT_PATH")

    try:
        config_data.set("DEFAULT", "config.project_root", temp_dir)
        os.environ["PROJECT_PATH"] = temp_dir

        cmd = [
            "python",
            "/app/orchestrator.py",
            "--skip-patches",         
            "--external-json"
        ]
        logger.info(f"Running orchestrator for counting issue in {temp_dir}")

        process = subprocess.Popen(
            cmd,
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        process.stdout.close()

        return_code = process.wait()
        if return_code != 0:
            logger.warning(f"Orchestrator returned non-zero exit code: {return_code}")

        json_file_path = config_data.get('DEFAULT', 'config.issues_path')

        # 4) Parse issues from the newly generated JSON
        file_issues = extract_issues_for_file(json_file_path, file_path)

        if file_issues and file_path in file_issues:
            new_count = file_issues[file_path]["Total issue count"]
            new_warnings_dict = file_issues[file_path]["warnings_dict_original"]
            logger.info(
                f"Orchestrator found {new_count} issues in {file_path}; "
                f"originally had {original_file_issue_count}"
            )

            # Determine if a new issue was introduced
            if new_count >= original_file_issue_count:
                introduced_new_issue = "True"
        else:
            introduced_new_issue = "build failed"

    except Exception as e:
        logger.error(f"Error checking new issues in {file_path}: {e}")
        introduced_new_issue = "build failed"

    finally:
        if old_project_root:
            config_data.set("DEFAULT", "config.project_root", old_project_root)
            logger.info(f"Restored project_root back to: {old_project_root}")
        if old_env_project_path:
            os.environ["PROJECT_PATH"] = old_env_project_path
        else:
            os.environ.pop("PROJECT_PATH", None)
    return {
        "introduced_new_issue": introduced_new_issue,
        "new_warnings_dict": new_warnings_dict
    }


def extract_issues_for_file(json_path: str, file_path: str):
    """
    Reads a JSON file and extracts issue data for the specified file.

    :param json_path: Path to the JSON file containing issue data.
    :param file_path: The file path for which issue data should be extracted.
    :return: A dictionary with issue counts and warning details for the specified file.
    """
    # Load JSON data from file
    with open(json_path, "r") as file:
        data = json.load(file)

    # Dictionary to store issues for the specified file
    issues_data = {"Total issue count": 0, "warnings_dict_original": defaultdict(int)}

    # Process the JSON data
    for entry in data:
        warning_name = entry["name"]
        for item in entry["items"]:
            textrange = item["textrange"]
            current_file = textrange["file"]

            # Only process the specified file
            if current_file == file_path:
                # Increment total issue count for the file
                issues_data["Total issue count"] += 1

                # Increment warning type count
                issues_data["warnings_dict_original"][warning_name] += 1

    issues_data["warnings_dict_original"] = dict(issues_data["warnings_dict_original"])

    return {file_path: issues_data} if issues_data["Total issue count"] > 0 else {}

def get_newly_introduced_issues(original_issue_dict, new_issue_dict):
    """
    Return a dictionary of only the issue types that have
    a higher count now than before, or did not exist originally.
    """
    newly_introduced = {}
    for issue_type, new_count in new_issue_dict.items():
        old_count = original_issue_dict.get(issue_type, 0)
        diff = new_count - old_count
        if diff > 0:
            newly_introduced[issue_type] = diff
    return newly_introduced


def transform_issues(json_file):
    """Transforms the JSON data into a dictionary with issue counts per file."""
    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    issue_warnings = defaultdict(lambda: {"Total issue count": 0, "warnings_dict_original": defaultdict(int)})
    
    for issue in json_data:
        issue_name = issue["name"]
        for item in issue["items"]:
            file_path = item["textrange"]["file"]
            issue_warnings[file_path]["Total issue count"] += 1
            issue_warnings[file_path]["warnings_dict_original"][issue_name] += 1
    
    # Convert defaultdicts to regular dicts
    return {k: {"Total issue count": v["Total issue count"], "warnings_dict_original": dict(v["warnings_dict_original"])} for k, v in issue_warnings.items()}

####################################
# Main Logic
####################################


def process_warning_worker(args):
    (
        warning,
        config_data,
        warning_dict,
        model_name,
        provider,
        api_key,
        build_tool,
        jdk_compiler_version,
        build_mode,
        base_project_path,
        diffs_output_dir,
        single_file,
        total_warnings,
        file_issue_types,
        issue_warnings,
        external_json
    ) = args

    local_stats = {
        'warning_id': warning['id'],
        'passed': False,
        'build_success': True,
        'validation_passed': False,
        'mvn_test_passed': True,
        'applicable_patch': True,
        'non_applicabale_diffs': 0,
        'validation_errors': 0,
        'compilation_or_test_errors': 0,
        'introduced_new_issue': False,
        'issue_name': "",
        'successful_patches': 0,
        'total_attempts': 0,
        'diff_file_name': None,
        'diff_file_path': None,
        'test_file_path': None,
        'keep_patch': True,
        'keep_test': True,
        'explanation': warning['explanation'],
        'input_tokens': [],
        'response_tokens': [],
        'new_warnings_distribution': {}
    }

    try:
        with tempfile.TemporaryDirectory(prefix=f"patch_{warning['id']}_") as temp_dir, tempfile.TemporaryDirectory(prefix=f"patch_{warning['id']}_build_") as temp_dir_for_build_tool:
            process_project_directory_core = temp_dir
            shutil.copytree(base_project_path, temp_dir, dirs_exist_ok=True)
            
            env = update_build_env_vars(temp_dir_for_build_tool, build_tool)
            local_config = copy.deepcopy(config_data)
            local_config.set('DEFAULT', 'config.project_root', temp_dir)
            test_generator = TestGenerator(temp_dir, local_config)
            if single_file is not None:
                sast = SASTOrchestrator(local_config, single_file=single_file.replace(os.environ.get('PROJECT_PATH'), temp_dir, 1))
                symbolic = SymbolicExecution(local_config, single_file=single_file.replace(os.environ.get('PROJECT_PATH'), temp_dir, 1))
            else:
                sast = SASTOrchestrator(local_config)
                symbolic = SymbolicExecution(local_config)
            mutable_warnings = warning_dict.copy()


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
                issue_resolved=True
                previous_generated_patch = None
                test_file_path, status, original_test_content = None, False, None

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

                    prompt = get_prompt(explanation, startLine, endLine, attempt, previous_generated_patch, SOLVE_COMMAND, extract_json_section)

                    os.makedirs(diffs_output_dir, exist_ok=True)

                    response = call_ai_with_retries_worker(provider, model_name, api_key, prompt, config_data)
                    if response is None:
                        logger.error(f"Failed to get AI response for warning ID {warning['id']} on attempt {attempt}.")
                        continue

                    generated_patch = extract_patch_from_response_worker(response['message'])


                    update_success = update_java_file_worker(full_file_path, extract_json_section, generated_patch)
                    if not update_success:
                        local_stats['applicable_patch'] = False
                        try:
                            with open(full_file_path, 'w') as f:
                                f.write(initial_content)
                            logger.info(f"Reverted patch in {full_file_path.split('/')[-1]} due to unsuccessful patch application.")
                        except Exception as e:
                            logger.error(f"Error while restoring original content to {full_file_path}: {e}")
                        continue
                
                    line_numbers = re.findall(r'"Line:(\d+)"', generated_patch)
    
                    line_numbers = list(map(int, line_numbers))
                    
                    if not line_numbers:
                        pass
                    else:   
                        min_line_number = min(line_numbers)
                        max_line_number = max(line_numbers)
                    previous_generated_patch = generated_patch
                    local_stats['input_tokens'].append(response.get('input_tokens', 0))
                    local_stats['response_tokens'].append(response.get('output_tokens', 0))

                    if single_file is not None:
                        try:
                            with open(full_file_path, 'r') as f:
                                new_file_content = f.read()
                        except Exception as e:
                            logger.error(f"Error reading file {full_file_path}: {e}")
                            return None
                        
                        # commented out for now as we are not generating test files for next release
                        # diff = difflib.unified_diff(
                        #     initial_content.splitlines(keepends=True),
                        #     new_file_content.splitlines(keepends=True),
                        #     fromfile=file_path,
                        #     tofile=file_path,
                        #     n=2
                        # )
                        # diff_text = ''.join(diff)
                        #full_import = derive_full_import_from_path(file_path=full_file_path)
                        #test_file_path, status, original_test_content = generate_test_file(
                            #java_file_path=full_file_path,
                            #updated_section=generated_patch,
                            #full_import=full_import,
                            #test_generator=test_generator,
                            #initial_section=extract_json_section,
                            #diff_content=diff_text
                        #)

                    if test_file_path and os.path.exists(test_file_path):
                        try:
                            with open(test_file_path, 'r') as f:
                                original_test_content = f.read()
                                logger.info(f"Saved original content for existing test file: {test_file_path}")
                        except Exception as e:
                            logger.error(f"Error reading original test file content: {e}")

                    logger.info(f"Process {os.getpid()} - Running '{build_tool} test' for warning ID {warning['id']}...")
                    output = run_tests_and_collect_output(build_tool, process_project_directory_core, env, jdk_compiler_version, build_mode)
                    context_for_diff_file = {
                            'initial_content': initial_content,
                            'full_file_path': full_file_path,
                            'file_path': file_path,
                            'attempt': attempt,
                            'diffs_output_dir': diffs_output_dir,
                            'warning_id': warning['id'],
                        }
                    decisions = validate_test_and_patch(test_file_path, output, build_tool, context_for_diff_file)
                    if not decisions.get('build_success', False):
                        try:
                            with open(full_file_path, 'r') as f:
                                new_file_content = f.read()
                        except Exception as e:
                            logger.error(f"Error reading file {full_file_path}: {e}")
                            return None
                        diff = difflib.unified_diff(
                            initial_content.splitlines(keepends=True),
                            new_file_content.splitlines(keepends=True),
                            fromfile=file_path,
                            tofile=file_path,
                            n=2
                        )
                        local_stats['build_success'] = False
                        local_stats['introduced_new_issue'] = False
                        if 'class, interface, or enum expected' in decisions['reason']:
                            try:
                                with open(full_file_path, 'w') as f:
                                    f.write(initial_content)
                                logger.info(f"Reverted patch in {full_file_path.split('/')[-1]} due to class, interface, or enum expected error.")
                            except Exception as e:
                                logger.error(f"Error while restoring original content to {full_file_path}: {e}")
                            
                            diff_text = ''.join(diff)
                            # Attempt removal of any extra braces
                            generated_patch = remove_last_extra_closing_brace(generated_patch)
                            logger.info("Build failed. Attempting to remove extra braces...")
                            update_success = update_java_file_worker(full_file_path, extract_json_section, generated_patch)
                            if update_success==False:
                                local_stats['applicable_patch'] = False
                                try:
                                    with open(full_file_path, 'w') as f:
                                        f.write(initial_content)
                                    logger.info(f"Reverted patch in {full_file_path.split('/')[-1]} due to unsuccessful patch application.")
                                except Exception as e:
                                    logger.error(f"Error while restoring original content to {full_file_path}: {e}")
                                continue
                            output_2 = run_tests_and_collect_output(build_tool, process_project_directory_core, env, jdk_compiler_version, build_mode)
                            decisions_2 = validate_test_and_patch(test_file_path, output_2, build_tool, context_for_diff_file)
                            if not decisions_2.get('build_success', False):
                                logger.warning("Even after parsing, build still fails.")
                                context_for_diff_file['diffs_output_dir'] = diffs_output_dir.replace("patches", "patches_with_build_failure")
                                create_diff(context_for_diff_file, f"failed at build process", decisions_2['reason'])
                                context_for_diff_file['diffs_output_dir'] = diffs_output_dir
                                logger.info(f"build failed for ID {warning['id']} due to: {decisions_2['reason']}")
                                previous_generated_patch += '\n\nPatch Failed due to: ' + decisions_2['reason']
                                local_stats['build_success'] = False
                            else:
                                logger.info("Build succeeded after removing braces!")
                            output = output_2
                            decisions = decisions_2
                        else:
                            context_for_diff_file['diffs_output_dir'] = diffs_output_dir.replace("patches", "patches_with_build_failure")
                            create_diff(context_for_diff_file, f"failed at build process", decisions['reason'])
                            context_for_diff_file['diffs_output_dir'] = diffs_output_dir
                    
                    issue_warnings = transform_issues(config_data.get("DEFAULT", "config.issues_path"))
                    
                    if decisions.get('build_success', False):
                        if external_json:
                            original_issue_dict_for_file = issue_warnings.get(file_path, {}).get("warnings_dict_original", {})
                            original_count_for_this_file = sum(original_issue_dict_for_file.values())
                            check_result = check_new_external_issues(file_path, original_count_for_this_file, temp_dir)
                        else:
                            original_issue_dict_for_file = file_issue_types.get(file_path, {})
                            original_count_for_this_file = sum(original_issue_dict_for_file.values())
                            with open(diffs_output_dir + '.lock', 'w') as lock_file:
                                try:
                                    fcntl.flock(lock_file, fcntl.LOCK_EX)
                                    check_result = check_new_issues(full_file_path, original_count_for_this_file)
                                finally:
                                    fcntl.flock(lock_file, fcntl.LOCK_UN)

                        introduced_new_issue = check_result["introduced_new_issue"]
                        new_warnings_dict = check_result["new_warnings_dict"]
                        newly_introduced_issues = get_newly_introduced_issues(
                            original_issue_dict_for_file,
                            new_warnings_dict
                        )
                        
                        if introduced_new_issue == "True":
                            logger.warning("New or equal number of issues introduced by patch. Reverting patch and retrying if attempts remain.")
                            local_stats['build_success'] = True
                            context = {
                                'initial_content': initial_content,
                                'full_file_path': full_file_path,
                                'file_path': file_path,
                                'attempt': attempt,
                                'diffs_output_dir': diffs_output_dir.replace("patches","patches_with_validation_errors"),
                                'warning_id': warning['id'],
                            }
                            if len(newly_introduced_issues) > 0:
                                issue_details = ", ".join([f"{issue}: {count}" for issue, count in newly_introduced_issues.items()])
                                log_helper = f'introduced_{len(newly_introduced_issues)}_issue'
                                create_diff(context, log_helper)
                                log_patch_name = f"{os.path.splitext(os.path.basename(full_file_path))[0]}_patch_{warning['id']}_attempt_{attempt}_{log_helper.replace(':', '-')}.diff"
                                logger.info(
                                    f"[IssueIntroductionStats] While patching '{name}', {log_patch_name} introduced {len(newly_introduced_issues)} new issue type(s): {issue_details}"
                                )        
                            else:
                                create_diff(context, f"did not solve the issue")
                            try:
                                with open(full_file_path, 'w') as f:
                                    f.write(initial_content)
                                logger.info(f"Reverted patch in {full_file_path.split('/')[-1]} due to newly introduced issues.")
                            except Exception as e:
                                logger.error(f"Error while restoring original content to {full_file_path}: {e}")

                            # 1) Mark stats
                            local_stats['introduced_new_issue'] = True
                            local_stats['validation_passed'] = True
                            local_stats['issue_name'] = name
                            local_stats['new_warnings_distribution'] = newly_introduced_issues

                            # 2) Incorporate the newly introduced issues into the next attempt's "previous_generated_patch"
                            if len(newly_introduced_issues) > 0:
                                introduced_issues_text = "\n\nThe previous patch introduced these new issues:\n"
                            else:
                                introduced_issues_text = "\n\nThe previous patch didn't solve the issue.\n"
                            for introduced_type, introduced_count in newly_introduced_issues.items():
                                introduced_issues_text += f"  - {introduced_type} (count: {introduced_count})\n"
                                new_issue_solve_command = ALL_WARNINGS.get(introduced_type, "")
                                if new_issue_solve_command:
                                    introduced_issues_text += f"    Possible fix command: {new_issue_solve_command}\n"
                                
                            if previous_generated_patch is None:
                                previous_generated_patch = ""
                            previous_generated_patch += introduced_issues_text
                            issue_resolved=False
                            continue
                        elif introduced_new_issue=="build failed":
                            local_stats['introduced_new_issue'] = False
                            local_stats['validation_passed'] = True
                            local_stats['build_success'] = False
                            issue_resolved=False
                        else:
                            local_stats['build_success'] = True
                            local_stats['introduced_new_issue'] = False
                            issue_resolved = True
                    context = {
                        'test_file_path': test_file_path,
                        'original_test_content': original_test_content,
                        'initial_content': initial_content,
                        'full_file_path': full_file_path,
                        'file_path': file_path,
                        'build_tool': build_tool,
                        'name': name,
                        'tag': tag,
                        'sast': sast,
                        'jdk_compiler_version': jdk_compiler_version,
                        'build_mode': build_mode,
                        'symbolic': symbolic,
                        'mutable_warnings': mutable_warnings,
                        'local_stats': local_stats,
                        'attempt': attempt,
                        'max_attempts': max_attempts,
                        'env': env,
                        'process_project_directory_core': process_project_directory_core,
                        'diffs_output_dir': diffs_output_dir,
                        'warning_id': warning['id'],
                        'decisions': decisions,
                        'status': status
                    }

                    compilation_result = handle_compilation_error(context, issue_resolved)
                    if compilation_result is True:
                        break
                    elif compilation_result is False:
                        continue
                    
                    if decisions.get('build_success', False):
                        validation_result = handle_build_success(context, issue_resolved)
                        if validation_result is True:
                            break
                        elif validation_result is False:
                            local_stats['validation_passed'] = True
                            continue
                    else:
                        local_stats['build_success'] = False
                        test_failure_result = handle_test_failures(context, issue_resolved)
                        local_stats['validation_passed'] = True
                        if test_failure_result is True:
                            break
                        elif test_failure_result is False:
                            continue

                if test_file_path and os.path.exists(test_file_path): # TODO: Update to check validation later
                    try:
                        project_path = os.environ.get('PROJECT_PATH')
                        if project_path:
                            relative_test_path = os.path.relpath(test_file_path, temp_dir)
                            new_test_path = os.path.join(project_path, '.ai4framework', 'tests', warning['id'], relative_test_path)
                            os.makedirs(os.path.dirname(new_test_path), exist_ok=True)
                            shutil.move(test_file_path, new_test_path)
                            local_stats['test_file_path'] = new_test_path
                            logger.info(f"Moved test file from {test_file_path} to {new_test_path}")
                    except Exception as e:
                        logger.error(f"Error moving test file to project path: {e}")
                else:
                    logger.info("Test file not moved because it does not exist.")

    except Exception as e:
        logger.error(f"Process {os.getpid()} - Unexpected error processing warning ID {warning['id']}: {e}")
    finally:
        if 'test_file_path' in locals() and 'original_test_content' in locals():
            if test_file_path and original_test_content is not None:
                revert_test_content({'test_file_path': test_file_path, 'original_test_content': original_test_content})
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Removed temporary directory: {temp_dir}")
        if temp_dir_for_build_tool:
            shutil.rmtree(temp_dir_for_build_tool, ignore_errors=True)
            logger.info(f"Removed process project directory: {temp_dir_for_build_tool}")

    return local_stats


def nested_defaultdict_int():
    return defaultdict(int)


class PatchGenerator:
    def __init__(self, config, warning_dict, num_of_rounds, single_file=None, external_json=None):
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        self.config = config
        self.provider = self.config.get('API', 'config.provider').lower()
        self.model_name = self.config.get('API', 'config.model')
        self.api_key = self.config.get('API', 'config.key', fallback='').strip()
        self.build_tool = self.config.get('DEFAULT', 'config.build_tool', fallback='maven').lower()
        self.jdk_compiler_version = self.config.get('DEFAULT', 'config.jdk_compiler_version')
        self.build_mode = self.config.get('DEFAULT', 'config.build_mode', fallback='online')
        self.single_file = single_file
        self.external_json = external_json
        if self.api_key == '':
            logger.warning("API key not found. Please set it in the configuration.")
            sys.exit(1)

        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.visualize_path = os.path.join(self.project_path, '.ai4framework', 'visualizations', str(int(time.time())))
        self.diffs_output_dir = self.config.get('DEFAULT', 'config.results_path')
        self.json_file_path = self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "single_rerun_issues.json") if self.single_file else self.config.get('DEFAULT', 'config.issues_path')
        self.cores_to_use = self.config.get('DEFAULT', 'config.parallel_workers', fallback='1')
        self.warnings = []
        self.compilation_or_test_errors = 0
        self.introduced_new_issue = 0
        self.validation_errors = 0
        self.successful_patches = 0
        self.non_applicabale_diffs = 0
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
        try:
            with open(self.json_file_path, 'w') as f:
                json.dump(self.warnings, f, indent=4)
                logger.info(f"Saved updated warnings JSON to {self.json_file_path}")
        except Exception as e:
            logger.error(f"Error saving updated warnings JSON: {e}")

    def generate_visualizations_and_metrics(self, elapsed_time):
        try:
            self.visualizer.update_metrics(self.model_name, {
                'total_issues': self.stats['total_issues'],
                'build_failures': self.compilation_or_test_errors,
                'introduced_new_issue': self.introduced_new_issue,
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
            logger.warning("Interruption during visualization and metrics generation. "+e)
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
            total_warnings = len(self.warnings)
            logger.info(f"Total warnings to process: {total_warnings}")
            
            file_issue_types = defaultdict(nested_defaultdict_int)

            for warning in self.warnings:
                issue_type_name = warning["name"]
                for item in warning["items"]:
                    textrange = item.get("textrange", {})
                    file_path = textrange.get("file")
                    if file_path:
                        file_issue_types[file_path][issue_type_name] += 1
            if self.external_json:
                cmd = [
                    "python",
                    "/app/orchestrator.py",
                    "--skip-patches",
                    "--external-json"
                ]
                logger.info(f"Running orchestrator with command for base issue counts")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )

                for line in process.stdout:
                    sys.stdout.write(line)
                process.stdout.close()

                # Wait for the process to finish
                return_code = process.wait()
                if return_code != 0:
                    logger.warning(f"Orchestrator returned non-zero exit code: {return_code}")
            issue_warnings = transform_issues(self.config.get("DEFAULT", "config.issues_path"))

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
                    self.jdk_compiler_version,
                    self.build_mode,
                    self.project_path,
                    self.diffs_output_dir,
                    self.single_file,
                    total_warnings,
                    file_issue_types,
                    issue_warnings,
                    self.external_json
                )
                args_list.append(args)

            num_workers = min(len(args_list), int(self.cores_to_use))
            logger.info(f"Starting multiprocessing with {num_workers} workers...")

            provessed_warnings = 0 # Only added for Plugin side for the notification bar

            with multiprocessing.Pool(processes=num_workers) as pool:
                for res in pool.imap_unordered(process_warning_worker, args_list):
                    provessed_warnings += 1 
                    if res is None:
                        logger.error("Worker returned None. Skipping...")
                        continue
                    if res['total_attempts'] == 2 or (res['total_attempts'] == 1 and not res['introduced_new_issue'] and res['build_success'] and res['applicable_patch']):
                        self.process_result(res)
                    self.save_warnings_json()

                    # This line is added specifically for the plugin side to enable the notification bar. Note that the print statement is essential, and the text format must include 'PROGRESS UPDATE:' to function correctly.
                    RESET_COLOR = "\033[0m"
                    BOLD_MAGENTA = "\033[1;35m"
                    print(f"{RESET_COLOR}{BOLD_MAGENTA}PROGRESS UPDATE: {provessed_warnings}/{total_warnings}{RESET_COLOR}", flush=True)

        except KeyboardInterrupt:
            logger.error("Keyboard interrupt detected in main. Saving progress and stopping the script gracefully.")
            self.save_warnings_json()
            raise
        except Exception as e:
            logger.error(f"Unexpected error in main: {e}", exc_info=True)
        finally:
            elapsed_time = time.time() - self.start_time
            self.stats['elapsed_time'] = elapsed_time
            if hasattr(self, 'issue_introduction_stats') and self.issue_introduction_stats:
                converted_stats = {
                    outer_key: dict(subdict)
                    for outer_key, subdict in self.issue_introduction_stats.items()
                }
                
                table_data = []
                for patched_issue, new_issues in converted_stats.items():
                    for introduced_issue, count in new_issues.items():
                        table_data.append([patched_issue, introduced_issue, count])
                
                table = tabulate(table_data, headers=["Patched Issue", "Introduced Issue", "Count"], tablefmt="grid")
                
                logger.info("Final updated issue introduction stats:\n%s", table)
            else:
                logger.info("No new issues were introduced during the patching process.")
            logger.info(f"Patch generation completed in {elapsed_time:.2f} seconds")
            try:
                self.save_warnings_json()
                self.generate_visualizations_and_metrics(elapsed_time)
            except Exception as e:
                logger.error(f"Error generating visualizations and metrics: {e}")

    def process_result(self, res):
        name = None
        for warning in self.warnings:
            if warning['id'] == res.get('warning_id'):
                name = warning['name']
                break

        if res.get('was_fixed', False) and name in self.warnings_dict:
            self.warnings_dict[name] -= 1

        self.stats['total_attempts'] += res.get('total_attempts', 0)
        if not res['introduced_new_issue'] and res['build_success'] and res['applicable_patch']:
            self.successful_patches += 1
        if not res.get('validation_passed', True):
            self.validation_errors += 1
        if not res.get('build_success', True):
            self.compilation_or_test_errors += 1
        if not res.get('applicable_patch', True):
            self.non_applicabale_diffs += 1
        if res.get('introduced_new_issue', False):
            self.introduced_new_issue += 1

            newly_introduced = res.get('new_warnings_distribution', {})
            patched_issue_type = res.get('issue_name', 'UnknownIssue')

            if not hasattr(self, 'issue_introduction_stats'):
                self.issue_introduction_stats = defaultdict(lambda: defaultdict(int))

            for introduced_type, introduced_count in newly_introduced.items():
                self.issue_introduction_stats[patched_issue_type][introduced_type] += introduced_count

            """ converted_stats = {
                outer_key: dict(subdict)
                for outer_key, subdict in self.issue_introduction_stats.items()
            }

            logger.info("Updated issue introduction stats:\n%s", json.dumps(converted_stats, indent=2)) """


        if 'input_tokens' in res and res['input_tokens']:
            self.input_tokens.extend(res['input_tokens'])
        if 'response_tokens' in res and res['response_tokens']:
            self.response_tokens.extend(res['response_tokens'])

        for warning in self.warnings:
            if warning['id'] == res.get('warning_id'):
                for item in warning['items']:
                    if 'patches' not in item:
                        item['patches'] = []
                    explanation = res.get('explanation', '')
                    if res.get('diff_file_name') and res.get('diff_file_path'):
                        item['patches'].append({
                            "path": res['diff_file_path'],
                            "explanation": explanation
                        })

                    if 'tests' not in item:
                        item['tests'] = []

                    test_entry = {}
                    if res.get('test_file_path'):
                        test_entry["path"] = res['test_file_path']
                        logger.info(f"Test file recorded at path: {res['test_file_path']}")

                    if test_entry:
                        item['tests'].append(test_entry)
                    else:
                        logger.info(f"No test information found for warning ID: {res.get('warning_id')}.")
                break