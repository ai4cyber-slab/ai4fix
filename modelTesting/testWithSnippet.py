import openai
import ollama
import json
import os
import subprocess
import shutil
from collections import defaultdict
import javalang
import time
import requests
from langchain_openai import ChatOpenAI
from gradio_client import Client
from huggingface_hub import InferenceClient
from dotenv import load_dotenv, find_dotenv
import time
import datetime

from AIModule import generate_text
from runMavenTest import run_maven_clean_test
from runMavenSpotbugs import run_maven_spotbugs

base_directory = "path_to_base_directory"
project_root = r'path_to_project_root'
maven_executable = r'path_to_maven_executable\mvn.cmd'
destination_xml_path = r'path_to_spotbugs\spotbugsXml.xml'
collect_warnings_script = r'path_to_collect_warnings_script\collectWarnings.py'



# Load vulnerability information from JSON file
json_file_path = 'path_to_vuln_json/spotbugs_dangerous_vulnerable_methods.json'
with open(json_file_path, 'r') as file:
    vulnerabilities = json.load(file)

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
vulnerabilities = vulnerabilities[:100]
run = 0
failed = 0
run_second = 0
failed_second = 0
errors = []
error_categories = defaultdict(int)
warning_type_counts = defaultdict(int)
error_type_counts = defaultdict(int)
i=0
count_warnings = []
maven_total_duration = 0
spotbugs_total_duration = 0
model_total_duration = 0

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

    IMPORTANT:
    - Provide the **entire fixed class** from the beginning to the end, ensuring all parts of the original class are included.
    - **Do not use placeholders or comments** to describe logic. All code logic must be fully implemented.
    - Do not include a "package" statement and do not use import statements for packages that are not explicitly mentioned in the provided class code.
    - Only use variables and functions previously mentioned in the code.

    Here is the current implementation of the method which contains the problematic method:

    ```java
    {vulnerability['codeSnippet']}
    ```

    and here's the class which contains it:
    ```java
    {vulnerability['classCode']}
    ```

    Please provide the complete and fully implemented fixed class below:
    """
    return input_text



""" def create_input_text(vulnerability, additional_info=''):
    input_text = f
    You are a software developer tasked with writing a patch for the following vulnerability in a Java application.

    Vulnerability Description:
    {vulnerability['explanation']}

    Your task is to provide the patched class implementation that fixes this vulnerability. {additional_info}

    Do not include "package" statement and do not use import statements for packages that are not explicitly mentioned in the provided class code. Only use variables and functions previously mentioned in the code.

    IMPORTANT:
    - Avoid using any external libraries or classes that are not already part of the project unless it is absolutely necessary.
    - Ensure that any new classes or methods introduced do not require additional dependencies.
    - If a necessary class is missing from the provided code, assume it is part of the existing project dependencies.
    - Provide the entire fixed class from the beginning to the end, ensuring all parts of the original class are included. Do not omit any part of the class.

    Ensure the response includes:
    - Class declaration
    - All fields and properties
    - All constructors
    - All methods (including getters and setters)
    - Any inner classes or enums
    - Proper closing braces for the class and methods

    Here is the current implementation of the method which contains the problematic method:

    ```java
    {vulnerability['codeSnippet']}
    ```

    and here's the class which contains it:

    ```java
    {vulnerability['classCode']}
    ```

    Please provide the complete fixed class below:
    
    return input_text

 """
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

    
def process_vulnerability(vulnerability, error_message, retry=False):
    global model_total_duration, spotbugs_total_duration, maven_total_duration, errors, error_categories, warning_type_counts, error_type_counts, run, failed, run_second, failed_second, vulnerabilities, project_root, maven_executable, destination_xml_path, collect_warnings_script
    returned_error_message = ""
    error_message = "taking into account the following feedback:" + error_message
    if error_message!="":
        input_text = create_input_text(vulnerability, error_message)
    else:
        input_text = create_input_text(vulnerability)
    try:
        start_time = time.time()
        output = generate_text(input_text)
        end_time = time.time()
        model_duration = end_time - start_time
        model_total_duration += model_duration
        print(output)
    except Exception as e:
        print(f"Failed to generate text: {e}")
        return

    patched_code = extract_code_from_output(output)

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
        start_time = time.time()
        result = run_maven_clean_test(maven_executable, project_root)
        end_time = time.time()
        maven_test_duration = end_time - start_time
        maven_total_duration += maven_test_duration

        line_counter = 0
        error_message_key = ""
        error_detected = False

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

                    error_type_counts[error_message_key] += 1
                    error_detected = True
                    break

        if error_detected:
            
            if retry:
                failed_second+=1
            else:
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

            if not retry:
                print(f"Retrying process_vulnerability for {vulnerability['fileName']}...")
                print(returned_error_message)
                process_vulnerability(vulnerability, returned_error_message, retry=True)
        else: 
            if retry:
                run_second+=1
            else:
                run += 1
            print("Maven tests passed.")

            start_time = time.time()
            result = run_maven_spotbugs(maven_executable, project_root)
            end_time = time.time()
            spotbugs_duration = end_time - start_time
            spotbugs_total_duration += spotbugs_duration

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

                result = subprocess.run(['python', './countSpotbugsWarnings.py'], capture_output=True, text=True)
                count_warnings.append(result.stdout)
                print(result.stdout)

                if result.returncode != 0:
                    print("countSpotbugsWarnings.py execution failed.")
                    print(result.stdout)
                    print(result.stderr)
                else:
                    print("countSpotbugsWarnings.py executed successfully.")
                    with open(json_file_path, 'r') as file:
                        vulnerabilities = json.load(file)
    print("--------------------------------")
    print(f"\nDIFFS APPLIED: {run}")
    print(f"DIFFS FAILED: {failed}\n")
    print("--------------------------------")


# generate 100 fixed classes
while i < 100:
    vulnerability = vulnerabilities[i]

    if not vulnerability:
        i += 1
        continue
    
    process_vulnerability(vulnerability, "", False)
    i += 1

print("--------------------------------")
print(f"\nDIFFS APPLIED: {run}")
print(f"DIFFS FAILED: {failed}\n")
print("--------------------------------")

print(f"--------------------------------\nAPPLIED FOR THE 2ND ITERATION: {run_second}")
print(f"\nFAILED TO APPLY FOR THE 2ND ITERATION:{failed_second}\n--------------------------------")

print("--------------------------------")
print("MAVEN ERROR TYPES:")
for error_type, count in error_type_counts.items():
    print(f"{error_type}: {count}")

with open('count_warnings.txt', 'w') as file:
    for warning in count_warnings:
        file.write(f"{warning}\n")


print(f"spotbugs total duration: {str(datetime.timedelta(seconds=spotbugs_total_duration))}")
print(f"maven test total duration: {str(datetime.timedelta(seconds=maven_total_duration))}")
print(f"model test total duration: {str(datetime.timedelta(seconds=model_total_duration))}")

print("--------------------------------")
print("Script execution completed.")

