import openai
# import ollama
import json
import os
import subprocess
import shutil
from collections import defaultdict
import numpy as np
import javalang
import time
import requests
# from langchain_openai import ChatOpenAI
# from gradio_client import Client
# from huggingface_hub import InferenceClient
from dotenv import load_dotenv, find_dotenv


# Base directory
base_directory = "C:\\Users\\HP\\slab\\ai4fix\\tester-project\\src\\main\\java"
project_root = r'C:\\Users\\HP\\slab\\ai4fix\\tester-project'
maven_executable = r'C:\\Program Files\\apache-maven-3.9.6-bin\\apache-maven-3.9.6\\bin\\mvn.cmd'
destination_xml_path = r'C:\\Users\\HP\\slab\\ai4fix\\tester-project\\out\\spotbugsXml.xml'
collect_warnings_script = r"C:\\Users\\HP\\slab\\ai4fix\\modelTesting\\collectWarnings.py"
data_file_path = r'C:\\Users\\HP\\slab\\ai4fix\\tester-project\\out\\patch_generation_data.csv'

# Load vulnerability information from JSON file
json_file_path = 'C:\\Users\\HP\\slab\\ai4fix\\tester-project\\out\\spotbugs_dangerous_vulnerable_methods.json'
with open(json_file_path, 'r') as file:
    vulnerabilities = json.load(file)

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
vulnerabilities = vulnerabilities[:100]
max_vulnerabilities = len(vulnerabilities)
run = 0
failed = 0
run_second = 0
failed_second = 0
errors = []
error_categories = defaultdict(int)
warning_type_counts = defaultdict(int)
error_type_counts = defaultdict(int)
i=0

data_points = []  # List to store (size_in_KLOC, time_taken) tuples (recent)

def get_code_size(code):
    # Function to estimate the size of code in KLOC
    lines = code.split('\n')
    return len(lines) / 1000.0  # Convert lines to KLOC

def measure_relevant_code_size(vulnerability):
    # Measure the size of the class containing the vulnerability
    class_code_size = get_code_size(vulnerability['classCode'])
    return class_code_size

bearer_token = os.getenv('HUGGINGFACE_API_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')

# hf models

API_URL = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3.1-405B-Instruct"
headers = {"Authorization": f"Bearer {bearer_token}"}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

""" def generate_text(input_text):
    try:
        output = query({
            "inputs": input_text,
            "parameters": {'return_full_text': False, 'temperature': 0.1, 'use_cache': False, 'wait_for_model': True}
        })

        print(output)

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
 """


# hf models inference api
""" def generate_text(input_text):
    answer = ""

    client = InferenceClient(
        "meta-llama/Meta-Llama-3.1-405B-Instruct",
        token=bearer_token,
    )

    for message in client.chat_completion(
        messages=[{"role": "user", "content": input_text}],
        max_tokens=2000,
        stream=True,
    ):
        answer+=(message.choices[0].delta.content)
    return(answer) """

# openai gpt models
# recommended version: pip openai==0.28
def generate_text(input_text, retries=3, wait=5):
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a software developer tasked with writing a patch for the following vulnerability."},
                    {"role": "user", "content": input_text}
                ]
            )
            return response['choices'][0]['message']['content']
        except openai.error.APIError as e:
            if e.http_status == 524:
                print(f"Attempt {attempt + 1}/{retries} failed with error: {e}. Retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("Failed to get a response after several retries")

def create_input_text(vulnerability, additional_info=''):
    input_text = f"""
    You are a software developer tasked with writing a patch for the following vulnerability in a Java application.

    Vulnerability Description:
    {vulnerability['explanation']}

    Your task is to provide the patched class implementation that fixes this vulnerability. {additional_info}

    Do not include "package" statement and do not use import statements for packages that are not explicitly mentioned in the provided class code. Only use variables and functions previously mentioned in the code.

    IMPORTANT: Provide the entire fixed class from the beginning to the end, ensuring all parts of the original class are included. Do not omit any part of the class.

    Here is the current implementation of the method which contains the problematic method (if there is):

    ```java
    {vulnerability['codeSnippet']}
    ```

    and here's the class which contains it:

    ```java
    {vulnerability['classCode']}
    ```

    Please provide the complete fixed class below:
    """
    return input_text


def extract_code_from_output(output):
    code_start = output.find("```")
    code_end = output.find("```", code_start + 3)
    if code_start != -1 and code_end != -1:
        cleaned_code = output[code_start + 3:code_end].strip()
        first_newline = cleaned_code.find('\n')
        if first_newline != -1 and cleaned_code[:first_newline].strip() in {"java", "python", "cpp", "javascript"}:
            cleaned_code = cleaned_code[first_newline:].strip()
        return cleaned_code
    else:
        return output.strip()

def find_method_bounds(tree, start_line, end_line):
    method_node = None
    for path, node in tree.filter(javalang.tree.MethodDeclaration):
        if node.position and start_line <= node.position.line <= end_line:
            method_node = node
            break
    return method_node

def find_class_bounds(tree, start_line, end_line):
    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        if node.position and start_line <= node.position.line <= end_line:
            return node
    return None

def apply_patch_to_file(file_path, start_line, end_line, patched_code):
    with open(file_path, 'r') as file:
        original_code = file.read()
        original_lines = original_code.splitlines(keepends=True)

    try:
        tree = javalang.parse.parse(original_code)
    except javalang.parser.JavaSyntaxError as e:
        print(f"Error parsing Java file: {file_path}")
        print(f"Syntax error details: {str(e)}")
        return None, None

    method_node = find_method_bounds(tree, start_line, end_line)
    class_node = find_class_bounds(tree, start_line, end_line)

    if method_node:
        method_start_line = method_node.position.line
        method_end_line = method_node.body[-1].position.line
    elif class_node:
        method_start_line = class_node.position.line
        method_end_line = class_node.body[-1].position.line
    else:
        print(f"Could not find method or class bounds in file: {file_path}")
        return None, None

    patched_code_lines = patched_code.splitlines(keepends=True)
    indent = ' ' * (len(original_lines[method_start_line - 1]) - len(original_lines[method_start_line - 1].lstrip()))
    patched_code_lines = [indent + line if line.strip() else line for line in patched_code_lines]

    # Remove any extra closing braces from the end of the patched code
    while patched_code_lines and patched_code_lines[-1].strip() == '}':
        patched_code_lines.pop()

    new_code_lines = original_lines[:method_start_line - 1] + patched_code_lines + original_lines[method_end_line:]
    new_code = ''.join(new_code_lines)

    with open(file_path, 'w') as file:
        file.write(new_code)

    return original_lines, new_code_lines


def apply_patch_to_class_file(original_code, class_start_line, class_end_line, patched_class_code):
    original_lines = original_code.split('\n')
    
    patched_lines = patched_class_code.split('\n') 

    if patched_lines[0].strip().startswith("```"):
        patched_lines = patched_lines[1:] 

    if patched_lines[-1].strip() == "```":
        patched_lines = patched_lines[:-1]
    
    new_code = (
        original_lines[:class_start_line - 1] +
        patched_lines +
        original_lines[class_end_line:] 
    )
    
    return '\n'.join(new_code)




# for second iteration
def process_vulnerability(vulnerability, error_message):
    global errors, error_categories, warning_type_counts, error_type_counts, run_second, failed_second, vulnerabilities, project_root, maven_executable, destination_xml_path, collect_warnings_script
    error_message = "taking into account the following feedback:" + error_message
    input_text = create_input_text(vulnerability, error_message)
    try:
        output = generate_text(input_text)
    except Exception as e:
        print(f"Failed to generate text: {e}")
        return

    patched_code = extract_code_from_output(output)

    print(f"Generated patched code for patch {i+1}:")
    print(patched_code)
    print("End of patched code")

    file_path = os.path.join(base_directory, *vulnerability['fileName'].replace('/', os.sep).split(os.sep))
    with open(file_path, 'r') as file:
        original_code = file.read()

    new_code = apply_patch_to_class_file(original_code, vulnerability['classStartLineNumber'], vulnerability['classEndLineNumber'], patched_code)
    
    with open(file_path, 'w') as file:
        file.write(new_code)

    print(f"Patch applied to: {file_path}")

    if not os.path.isdir(project_root):
        print(f"Error: The directory '{project_root}' does not exist or is not a directory.")
    else:
        result = subprocess.run([maven_executable, 'clean', 'test'], cwd=project_root, capture_output=True, text=True)
        line_counter = 0
        error_message_key=""
        print("\nMaven clean test output:")
        error_detected = False
        for line in result.stdout.split("\n"):
            if "[ERROR]" in line:
                line_counter += 1
                if line_counter == 2:
                    print(line)
                    split_line = line.split("] ")
                    if len(split_line) > 2:
                        error_message = line.split("] ")[2]
                        error_type_counts[error_message] += 1
                        error_detected = True
                        break
                    else:
                        error_message = line.split("] ")[1]
                        error_type_counts[error_message] += 1
                        error_detected = True
                        break

        for line in result.stderr.split("\n"):
            if "[ERROR]" in line:
                line_counter += 1
                if line_counter == 2:
                    print(line)
                    error_message = line.split("] ")[2]
                    error_type_counts[error_message] += 1
                    error_detected = True
                    break

        if error_detected:
            failed_second += 1
            print(f"Reverting changes...")
            with open(file_path, 'w') as file:
                file.write(original_code)
            print(f"Reverted changes in: {file_path}")

            error_output = result.stdout + result.stderr
            if error_output:
                error_lines = error_output.splitlines()
                error_message = "\n".join(error_lines)
                errors.append(error_message)

                categorized = False
                for line in error_lines:
                    if "COMPILATION ERROR" in line:
                        error_categories["Compilation Errors"] += 1
                        categorized = True
                        break
                    elif "BUILD FAILURE" in line:
                        error_categories["Build Failures"] += 1
                        break
                if not categorized:
                    error_categories["Other Errors"] += 1
            else:
                errors.append("Unknown error occurred.")
                error_categories["Unknown Errors"] += 1
        else:
            run_second += 1
            print("Maven tests passed.")

            result = subprocess.run([maven_executable, 'spotbugs:spotbugs'], cwd=project_root, capture_output=True, text=True)

            if result.returncode != 0:
                print("SpotBugs execution failed.")
                print(result.stdout)
                print(result.stderr)
            else:
                print("SpotBugs execution completed successfully.")
                source_xml_path = os.path.join(project_root, 'target', 'spotbugsXml.xml')
                
                try:
                    shutil.move(source_xml_path, destination_xml_path)
                    print(f"Moved SpotBugs XML to {destination_xml_path}")
                except Exception as e:
                    print(f"Error moving SpotBugs XML: {e}")

                result = subprocess.run(['python', collect_warnings_script], capture_output=True, text=True)

                if result.returncode != 0:
                    print("collectWarnings.py execution failed.")
                    print(result.stdout)
                    print(result.stderr)
                else:
                    print("collectWarnings.py executed successfully.")
                    with open(json_file_path, 'r') as file:
                        vulnerabilities = json.load(file)
    print(f"\nDIFFS APPLIED FOR THE SECOND ITERATION: {run_second}")
    print("--------------------------------")
    print(f"DIFFS FAILED FOR THE SECOND ITERATION: {failed_second}\n")

with open(data_file_path, 'w') as f:
    f.write("code_size,time_taken\n")  # Write the header
    # generate 100 fixed classes
    while i < max_vulnerabilities:
        vulnerability = vulnerabilities[i]
        input_text = create_input_text(vulnerability)
        # Start timing the patch generation
        start_time = time.time()
        try:
            output = generate_text(input_text)
            print(output)
        except Exception as e:
            print(f"Failed to generate text: {e}")
            continue
        end_time = time.time()
        patch_generation_time = end_time - start_time

        # Estimate the size of the relevant code
        relevant_code_size = measure_relevant_code_size(vulnerability)

        # Store the data point
        # data_points.append((relevant_code_size, patch_generation_time))
        f.write(f"{relevant_code_size},{patch_generation_time}\n")
        print(f"Code size: {relevant_code_size} KLOC, Time taken: {patch_generation_time} seconds")

        patched_code = extract_code_from_output(output)

        """ print(f"Generated patched code for patch {i+1}:")
        print(patched_code)
        print("End of patched code") """

        file_path = os.path.join(base_directory, *vulnerability['fileName'].replace('/', os.sep).split(os.sep))
        with open(file_path, 'r') as file:
            original_code = file.read()

        new_code = apply_patch_to_class_file(original_code, vulnerability['classStartLineNumber'], vulnerability['classEndLineNumber'], patched_code)
        
        with open(file_path, 'w') as file:
            file.write(new_code)

        print(f"Patch applied to: {file_path}")

        if not os.path.isdir(project_root):
            print(f"Error: The directory '{project_root}' does not exist or is not a directory.")
        else:
            result = subprocess.run([maven_executable, 'clean', 'test'], cwd=project_root, capture_output=True, text=True)
            line_counter = 0
            error_message_key=""
            print("\nMaven clean test output:")
            error_detected = False
            for line in result.stdout.split("\n"):
                if "[ERROR]" in line:
                    line_counter += 1
                    if line_counter == 2:
                        print(line)
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

            # Process stderr
            for line in result.stderr.split("\n"):
                if "[ERROR]" in line:
                    line_counter += 1
                    if line_counter == 2:
                        print(line)
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

                        error_type_counts[error_message_key] += 1
                        error_detected = True
                        break

            if error_detected:
                failed += 1
                print(f"Reverting changes...")
                with open(file_path, 'w') as file:
                    file.write(original_code)
                print(f"Reverted changes in: {file_path}")

                error_output = result.stdout + result.stderr
                if error_output:
                    error_lines = error_output.splitlines()
                    error_message = "\n".join(error_lines)
                    errors.append(error_message)

                    categorized = False
                    for line in error_lines:
                        if "COMPILATION ERROR" in line:
                            error_categories["Compilation Errors"] += 1
                            categorized = True
                            break
                        elif "BUILD FAILURE" in line:
                            error_categories["Build Failures"] += 1
                            break
                    if not categorized:
                        error_categories["Other Errors"] += 1
                else:
                    errors.append("Unknown error occurred.")
                    error_categories["Unknown Errors"] += 1
                process_vulnerability(vulnerability, returned_error_message)
            else:
                run += 1
                print("Maven tests passed.")

                result = subprocess.run([maven_executable, 'spotbugs:spotbugs'], cwd=project_root, capture_output=True, text=True)

                if result.returncode != 0:
                    print("SpotBugs execution failed.")
                    print(result.stdout)
                    print(result.stderr)
                else:
                    print("SpotBugs execution completed successfully.")
                    source_xml_path = os.path.join(project_root, 'target', 'spotbugsXml.xml')
                    try:
                        shutil.move(source_xml_path, destination_xml_path)
                        print(f"Moved SpotBugs XML to {destination_xml_path}")
                    except Exception as e:
                        print(f"Error moving SpotBugs XML: {e}")

                    result = subprocess.run(['python', collect_warnings_script], capture_output=True, text=True)

                    if result.returncode != 0:
                        print("collectWarnings.py execution failed.")
                        print(result.stdout)
                        print(result.stderr)
                    else:
                        print("collectWarnings.py executed successfully.")
                        with open(json_file_path, 'r') as file:
                            vulnerabilities = json.load(file)
        i += 1

        print(f"\nDIFFS APPLIED: {run}")
        print("--------------------------------")
        print(f"DIFFS FAILED: {failed}\n")


print(f"-----------\nAPPLIED FOR THE 2ND ITERATION: {run_second}\n")
print(f"\nFAILED TO APPLY FOR THE 2ND ITERATION:{failed_second}\n-----------")

print("ERROR CATEGORIES:")
for category, count in error_categories.items():
    print(f"{category}: {count}")

print("--------------------------------")
print("WARNING TYPE COUNTS:")
for warning_type, count in warning_type_counts.items():
    print(f"{warning_type}: {count}")

print("--------------------------------")
print("MAVEN ERROR TYPES:")
for error_type, count in error_type_counts.items():
    print(f"{error_type}: {count}")

print("--------------------------------")
print("Script execution completed.")





# # Extrapolation
# data_points = np.array(data_points)
# x = data_points[:, 0]  # Code sizes in KLOC
# y = data_points[:, 1]  # Times in seconds

# # Fit a linear regression model
# coefficients = np.polyfit(x, y, 1)
# linear_model = np.poly1d(coefficients)

# # Predict time for 10 KLOC
# predicted_time_10KLOC = linear_model(10)
# print(f"data gathered: {data_points}")
# print(f"Estimated time to generate patch for 10KLOC using Extrapolation: {predicted_time_10KLOC} seconds")