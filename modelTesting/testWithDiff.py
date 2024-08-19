import json
import os
import subprocess
import openai
import shutil
from collections import defaultdict
import requests
import re
import time
from dotenv import load_dotenv, find_dotenv

run = 0
failed = 0
run_second = 0
failed_twice = 0
test_run_second = 0
test_failed_twice = 0
test_run = 0
test_failed = 0
error_type_counts = defaultdict(int)
original_directory = os.getcwd()
base_directory = "path_to_base_directory"
git_bash_path = "path_to_git_bash/bash.exe"
json_file_path = 'path_to_vuln_json/spotbugs_dangerous_vulnerable_methods.json'
project_root = r'path_to_project_root'
maven_executable = r'path_to_maven_executable\mvn.cmd'
destination_xml_path = r'path_to_spotbugs\spotbugsXml.xml'
collect_warnings_script = r'path_to_collect_warnings_script\collectWarnings.py'
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
bearer_token = os.getenv('HUGGINGFACE_API_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')

API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
headers = {"Authorization": f"Bearer {bearer_token}"}

# hf models
def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

def generate_text(input_text):
    try:
        output = query({
            "inputs": input_text,
            "parameters": {'return_full_text': False, 'temperature': 0.1, 'use_cache': False, 'wait_for_model': False}
        })

        if isinstance(output, list) and len(output) > 0 and 'generated_text' in output[0]:
            generated_text = output[0]['generated_text']
            print(generated_text)
            return generated_text
        else:
            print("No generated text available.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# gpt-4o
"""
def generate_text(input_text):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a software developer tasked with writing a patch for the following vulnerability."},
            {"role": "user", "content": input_text}
        ]
    )
    return response['choices'][0]['message']['content']  """

def create_input_text(vulnerability, additional_info=""):
    input_text = f"""
    You are a skilled software developer assigned to create a patch for a security vulnerability in a Java application.
    Your task is to provide an accurate diff to fix the vulnerability, taking into account the following feedback: {additional_info}
    Ensure that the diff is properly formatted and only includes necessary changes.

    Vulnerability Description:
    {vulnerability['explanation']}

    Filename: {vulnerability['fileName']}
    Start Line: {vulnerability.get('startLineNumber', '')}
    End Line: {vulnerability.get('endLineNumber', '')}

    Below is the current implementation of the method:
    {vulnerability['codeSnippet']}


    Example diff structure:
    ```
    --- filename
    +++ filename
    @@ -<line number>,<context lines> +<line number>,<context lines> @@
     <context line>
    -<removed line>
    +<added line>
     <context line>
    ```

    Ensure the diff is as follows:
    - The filename is correctly mentioned.
    - '@@' symbols are used correctly to denote changes.
    - Only one necessary lines are included for context.
    - Correctly indicate removed and added lines.
    - No assumptions like "//other methods"
    - provide the diff between ``` and ```

    Provide the output in the .diff format adhering to the above example and instructions.
    """
    return input_text



def convert_to_unix_path(path):
    return path.replace('\\', '/')


def apply_indentation(diff, snippet):
    snippet_lines = snippet.splitlines()
    leading_spaces = {}

    for line in snippet_lines:
        stripped_line = line.strip()
        leading_spaces[stripped_line] = len(line) - len(line.lstrip())

    pattern_minus = re.compile(r'^-(?!-)(.*)', re.MULTILINE)
    pattern_plus = re.compile(r'^\+(?!\+)(.*)', re.MULTILINE)
    indent = ''

    def adjust_minus(match):
        nonlocal indent
        line_content = match.group(1).lstrip()
        indent = ' ' * leading_spaces.get(line_content, 0)
        return f"-{indent}{line_content}"

    def adjust_plus(match):
        line_content = match.group(1).lstrip()
        return f"+{indent}{line_content}"

    adjusted_diff = re.sub(pattern_minus, adjust_minus, diff)
    adjusted_diff = re.sub(pattern_plus, adjust_plus, adjusted_diff)

    return adjusted_diff

def clean_diff_content(diff_content, file_name, vulnerability):
    cleaned_lines = []
    changes = []
    context_lines = []
    diff_started = False
    original_start = 0
    new_start = 0
    original_lines = 0
    new_lines = 0

    # Remove leading spaces from each line in the diff content
    diff_content = "\n".join(line.lstrip() for line in diff_content.splitlines())

    original_file_lines = vulnerability['codeSnippet'].splitlines()

    for line in diff_content.splitlines():
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("diff --git") or line.startswith("index") or line.startswith("Index") or line.startswith("===="):
            continue
        if line.startswith("@@"):
            if changes:
                cleaned_lines.append(f"@@ -{original_start},{original_lines} +{new_start},{new_lines} @@")
                cleaned_lines.extend(changes)
                changes = []
            diff_started = True
            header_info = line.split(' ')[1:3]
            original_info = header_info[0].split(',')
            new_info = header_info[1].split(',')
            original_start = int(original_info[0][1:])
            new_start = int(new_info[0][1:])
            original_lines = 0
            new_lines = 0
            context_lines = []
            continue

        if diff_started:
            if line.startswith("-") or line.startswith("+"):
                line_content = line[1:].rstrip()
                line_index = original_start + original_lines - 1
                if line.startswith("-") and line_index < len(original_file_lines):
                    original_line = original_file_lines[line_index]
                    trailing_spaces = len(original_line) - len(original_line.rstrip())
                else:
                    trailing_spaces = 0

                modified_line = f"{line[0]}{line_content}{' ' * trailing_spaces}"
                changes.extend(context_lines)
                context_lines = []
                changes.append(modified_line)
                if line.startswith("-"):
                    original_lines += 1
                if line.startswith("+"):
                    new_lines += 1
            else:
                if changes:
                    context_lines.append(line)
                    original_lines += 1
                    new_lines += 1

    if changes:
        cleaned_lines.append(f"@@ -{original_start},{original_lines} +{new_start},{new_lines} @@")
        cleaned_lines.extend(changes)

    cleaned_lines.insert(0, f"+++ {file_name}")
    cleaned_lines.insert(0, f"--- {file_name}")

    final_diff = "\n".join(line for line in cleaned_lines if line.strip()) + "\n"
    final_diff = apply_indentation(final_diff, vulnerability['codeSnippet'])

    return final_diff


# Load vulnerability information from JSON file
with open(json_file_path, 'r') as file:
    vulnerabilities = json.load(file)

vulnerabilities = vulnerabilities[:100]

# Helper function to revert a file to its original state
def revert_file(file_path, original_lines):
    with open(file_path, 'w') as file:
        file.writelines(original_lines)
    print(f"Reverted changes in: {file_path}")


# process vulnerability for second iteration
def process_vulnerability(vulnerability, error_message):
    global run_second, failed_twice, test_run_second, test_failed_twice, error_type_counts, project_root, maven_executable, destination_xml_path, collect_warnings_script
    print(f"-----------\nRUN:{run}\n-----------")
    print(f"\nFAILED:{failed}\n-----------")
    input_text = create_input_text(vulnerability, error_message)
    output = generate_text(input_text)

    if "```diff" in output:
        diff_start = output.find("```diff")
        diff_end = output.find("```", diff_start + 7)
        diff_content = output[diff_start + 7:diff_end].strip()
    else:
        diff_start = output.find("```")
        diff_end = output.find("```", diff_start + 3)
        diff_content = output[diff_start + 3:diff_end].strip()

    print("Generated diff content for patch:")
    print(diff_content)
    print("End of diff content")

    file_path = vulnerability['fileName']
    full_file_path = os.path.join(base_directory, file_path)
    dir_path = os.path.dirname(full_file_path)
    file_name = os.path.basename(full_file_path)

    try:
        cleaned_diff_content = clean_diff_content(diff_content, file_name, vulnerability)
    except Exception as e:
        failed_twice += 1
        print(e)
        return

    patch_file_path = os.path.join(original_directory, 'patch.diff')
    with open(patch_file_path, 'w') as patch_file:
        patch_file.write(cleaned_diff_content)

    print(f"\nPatch saved to: {patch_file_path}")
    print(f"Output for patch:", output)

    os.chdir(dir_path)
    print(f"Changed directory to: {dir_path}")

    unix_patch_file_path = convert_to_unix_path(os.path.abspath(patch_file_path))

    try:
        original_lines = None
        with open(full_file_path, 'r') as file:
            original_lines = file.readlines()
        result = subprocess.run([git_bash_path, '-c', f'patch -p0 < {unix_patch_file_path}'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Patch {patch_file_path} applied successfully.")
            run_second += 1

            if not os.path.isdir(project_root):
                print(f"Error: The directory '{project_root}' does not exist or is not a directory.")
                return

            result = subprocess.run([maven_executable, 'clean', 'test'], cwd=project_root, capture_output=True, text=True)
            line_counter = 0
            print("\nMaven clean test output:")
            for line in result.stdout.split("\n"):
                if "[ERROR]" in line:
                    line_counter += 1
                    if "cannot" in line:
                        if line_counter == 2:
                            print(line)
                            split_line = line.split("] ")
                            if len(split_line) > 2:
                                error_message_key = split_line[2]
                                error_message = error_message_key
                            else:
                                error_message = line
                            
                            lines = result.stdout.split("\n")
                            next_line_index = lines.index(line) + 1
                            if next_line_index < len(lines):
                                next_line = lines[next_line_index]
                                error_message += " " + next_line
                            
                            error_type_counts[error_message_key] += 1
                            break
                    else:
                        if line_counter == 2:
                            print(line)
                            split_line = line.split("] ")
                            if len(split_line) > 2:
                                error_message = split_line[2]
                            else:
                                error_message = line
                            error_type_counts[error_message] += 1
                            break
            if result.returncode == 0:
                print("Maven tests passed.")
                test_run_second += 1
                result = subprocess.run([maven_executable, 'spotbugs:spotbugs'], cwd=project_root, capture_output=True, text=True)
                if result.returncode == 0:
                    print("SpotBugs analysis completed successfully.")
                    source_xml_path = os.path.join(project_root, 'target', 'spotbugsXml.xml')
                    
                    try:
                        shutil.move(source_xml_path, destination_xml_path)
                        print(f"Moved SpotBugs XML to {destination_xml_path}")

                        result = subprocess.run(['python', collect_warnings_script], capture_output=True, text=True)
                        if result.returncode == 0:
                            print("collectWarnings.py executed successfully.")
                        else:
                            print("collectWarnings.py execution failed.")
                            print(result.stdout)
                            print(result.stderr)
                    except Exception as e:
                        print(f"Error moving SpotBugs XML: {e}")
                else:
                    print("SpotBugs analysis failed.")
                    print(result.stdout)
                    print(result.stderr)
            else:
                test_failed_twice += 1
                revert_file(full_file_path, original_lines)
                return
        else:
            print(f"Failed to apply patch {patch_file_path}.")
            failed_twice += 1
            print("Standard Output:")
            print(result.stdout)
            print("Standard Error:")
            print(result.stderr)
            return

    except Exception as e:
        print(f"An error occurred while applying patch {patch_file_path}: {e}")
        return


# main patching function
for i, vulnerability in enumerate(vulnerabilities):
    print(f"-----------\nRUN:{run}\n-----------")
    print(f"\nFAILED:{failed}\n-----------")
    input_text = create_input_text(vulnerability)
    output = generate_text(input_text)

    if "```diff" in output:
        diff_start = output.find("```diff")
        diff_end = output.find("```", diff_start + 7)
        diff_content = output[diff_start + 7:diff_end].strip()
    else:
        diff_start = output.find("```")
        diff_end = output.find("```", diff_start + 3)
        diff_content = output[diff_start + 3:diff_end].strip()

    print(f"Generated diff content for patch {i + 1}:")
    print(diff_content)
    print("End of diff content")

    # File name and relative path
    file_path = vulnerability['fileName']
    full_file_path = os.path.join(base_directory, file_path)
    dir_path = os.path.dirname(full_file_path)
    file_name = os.path.basename(full_file_path)

    # Clean the diff content
    try:
        cleaned_diff_content = clean_diff_content(diff_content, file_name, vulnerability)
    except Exception as e:
        failed= failed+1
        print(e)
        continue

    # Saving the diff
    patch_file_path = os.path.join(original_directory, f'patch.diff')
    with open(patch_file_path, 'w') as patch_file:
        patch_file.write(cleaned_diff_content)

    print(f"\nPatch saved to: {patch_file_path}")
    print(f"Output for patch:", output)

    # Change to the directory of the file
    os.chdir(dir_path)
    print(f"Changed directory to: {dir_path}")

    # Convert patch file path to Unix style
    unix_patch_file_path = convert_to_unix_path(os.path.abspath(patch_file_path))

    # Apply the patch using patch -p0 with Git Bash
    try:
        # Save the original file content in case we need to revert
        original_lines = None
        with open(full_file_path, 'r') as file:
            original_lines = file.readlines()
        result = subprocess.run([git_bash_path, '-c', f'patch -p0 < {unix_patch_file_path}'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Patch {patch_file_path} applied successfully.")
            run = run + 1

            if not os.path.isdir(project_root):
                print(f"Error: The directory '{project_root}' does not exist or is not a directory.")
                continue

            result = subprocess.run([maven_executable, 'clean', 'test'], cwd=project_root, capture_output=True, text=True)
            line_counter = 0
            print("\nMaven clean test output:")
            for line in result.stdout.split("\n"):
                if "[ERROR]" in line:
                    line_counter += 1
                    if "cannot" in line:
                        if line_counter == 2:
                            print(line)
                            split_line = line.split("] ")
                            if len(split_line) > 2:
                                error_message_key = split_line[2]
                                error_message = error_message_key
                            else:
                                error_message = line
                            
                            lines = result.stdout.split("\n")
                            next_line_index = lines.index(line) + 1
                            if next_line_index < len(lines):
                                next_line = lines[next_line_index]
                                error_message += " " + next_line
                            
                            error_type_counts[error_message_key] += 1
                            print("Maven tests failed. Reverting changes...")
                            revert_file(full_file_path, original_lines)
                            process_vulnerability(vulnerability, error_message)
                            break
                    else:
                        if line_counter == 2:
                            print(line)
                            split_line = line.split("] ")
                            if len(split_line) > 2:
                                error_message = split_line[2]
                            else:
                                error_message = line
                            error_type_counts[error_message] += 1
                            print("Maven tests failed. Reverting changes...")
                            revert_file(full_file_path, original_lines)
                            process_vulnerability(vulnerability, error_message)
                            break
            if result.returncode == 0:
                print("Maven tests passed.")
                test_run += 1
                # Run SpotBugs analysis
                result = subprocess.run([maven_executable, 'spotbugs:spotbugs'], cwd=project_root, capture_output=True, text=True)
                if result.returncode == 0:
                    print("SpotBugs analysis completed successfully.")

                    # Move the SpotBugs XML report
                    source_xml_path = os.path.join(project_root, 'target', 'spotbugsXml.xml')
                    try:
                        shutil.move(source_xml_path, destination_xml_path)
                        print(f"Moved SpotBugs XML to {destination_xml_path}")

                        # Run collectWarnings.py
                        result = subprocess.run(['python', collect_warnings_script], capture_output=True, text=True)
                        if result.returncode == 0:
                            print("collectWarnings.py executed successfully.")
                        else:
                            print("collectWarnings.py execution failed.")
                            print(result.stdout)
                            print(result.stderr)
                    except Exception as e:
                        print(f"Error moving SpotBugs XML: {e}")
                else:
                    print("SpotBugs analysis failed.")
                    print(result.stdout)
                    print(result.stderr)
            else:
                print("Maven tests failed. Reverting changes...")
                test_failed +=1
                revert_file(full_file_path, original_lines)
                continue
        else:
            print(f"Failed to apply patch {patch_file_path}.")
            failed = failed + 1
            print("Standard Output:")
            print(result.stdout)
            print("Standard Error:")
            print(result.stderr)
            continue

    except Exception as e:
        print(f"An error occurred while applying patch {patch_file_path}: {e}")
        continue

# information of the patching
print("All patches processed.")

print(f"-----------\nRUN: {run}\n-----------")
print(f"\nFAILED: {failed}\n-----------")

print(f"-----------\nRUN FOR THE 2ND ITERATION: {run_second}\n-----------")
print(f"\nFAILED TWICE:{failed_twice}\n-----------")

print(f"\n-----------\nRUN WITH TEST:{test_run}\n-----------")
print(f"\nFAILED WITH TEST:{test_failed}\n-----------")

print(f"\n-----------\nRUN WITH SECOND TEST TOO: {test_run_second}\n-----------")
print(f"\nFAILED WITH TEST TWICE:{test_failed_twice}\n-----------")

print("--------------------------------")
print("MAVEN ERROR TYPES:")
for error_type, count in error_type_counts.items():
    print(f"{error_type}: {count}")