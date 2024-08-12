import json
import os

# Function to extract the relevant snippet from a file
def extract_snippet(file_path, start_line, end_line):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        snippet = lines[start_line-1:end_line]
        return ''.join(snippet)

# Function to process the JSON data and create temp files with relevant code parts
def process_json_and_create_temp_files(json_data, base_dir, temp_dir):
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    for file_info in json_data['security_relevant_files']:
        file_path = os.path.join(base_dir, file_info['file_path'])
        for index, line_position in enumerate(file_info['security_relevant_lines']):
            start_line = line_position['start_position']
            end_line = line_position['end_position']

            # Extract the snippet
            snippet = extract_snippet(file_path, start_line, end_line)

            # Create a temporary file to store the snippet
            temp_file_name = f"{os.path.basename(file_path).split('.')[0]}_part_{index+1}.java"
            temp_file_path = os.path.join(temp_dir, temp_file_name)
            with open(temp_file_path, 'w') as temp_file:
                temp_file.write(f"// Extracted from {file_path}, lines {start_line}-{end_line}\n")
                # temp_file.write("public class TempClass {\n")
                # temp_file.write("    public void tempMethod() {\n")
                temp_file.write(snippet)
                # temp_file.write("    }\n")
                # temp_file.write("}\n")

            print(f"Created temporary file: {temp_file_path}")



with open('31644c1ad941f311b9664603cd531cdb3eda0fcd.json', 'r') as json_file:
    json_data = json.load(json_file)
    base_dir = json_data['repository_path']
    temp_dir = './temp_files'

process_json_and_create_temp_files(json_data, base_dir, temp_dir)

