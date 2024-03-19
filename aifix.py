from dotenv import load_dotenv
import openai
import os
import json
import sys
import subprocess

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def generate_diff(java_code, issue_data):
    issue_data_dict = json.loads(issue_data)
    text_range = issue_data_dict[0]['items'][0]['textRange']
    start_line = text_range['startLine']
    end_line = text_range['endLine']
    
    relevant_lines = java_code.split('\n')[start_line-1:end_line]
    relevant_code = '\n'.join(relevant_lines)

    prompt = (
        f"I have a Java file, and I need to generate a diff for a specific issue. "
        f"The issue is in the following lines (lines {start_line} to {end_line}):\n\n"
        f"relevant code: {relevant_code}\n\n"
        f"Here's the full Java file so you know which lines needs to be changed and create a full diff file: {java_code}\n\n"
        f"The rest of the file should remain unchanged. Here is the detailed issue information:\n"
        f"{issue_data}\n\n"
        f"Based on this, please generate the necessary diff snippet for these lines only."
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']

def generate_explanation(diff_content):
    prompt = (
        f"Given this diff:\n{diff_content}\n\n"
        f"Summarize the purpose of these changes in a short single sentence:"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=40
    )
    return response.choices[0].message['content']


def write_to_file(file_path, content):
    with open(file_path, 'w') as file:
        file.write(content)

def extract_diff_content(full_content):
    start_marker = "```diff"
    end_marker = "```"
    start = full_content.find(start_marker)
    end = full_content.find(end_marker, start + 1)

    if start != -1 and end != -1:
        return full_content[start + len(start_marker):end].strip()
    else:
        return full_content
    
def get_relative_path(subject_project_path, current_file_path):
    normalized_project_path = os.path.normpath(subject_project_path)
    normalized_file_path = os.path.normpath(current_file_path)

    relative_path = os.path.relpath(normalized_file_path, normalized_project_path)

    return relative_path

def replace_diff_paths(diff_content, relative_path):
    lines = diff_content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('--- ') or line.startswith('+++ '):
            parts = line.split(' ')
            if len(parts) > 1:
                new_lines.append(parts[0] + ' ' + relative_path)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)

def run_command(command, working_directory):
    try:
        subprocess.run(command, shell=True, check=True, cwd=working_directory)
    except subprocess.CalledProcessError as e:
        sys.exit(1)

def main():
    if len(sys.argv) < 7:
        sys.exit(1)

    java_file_path = sys.argv[1]
    json_file_path = sys.argv[2]
    patches_dir_path = sys.argv[3]
    subject_project_path = sys.argv[4]
    analyzer_parameters = sys.argv[5] + " -cu=" + java_file_path
    analyzer_exe_path = sys.argv[6]

    run_command(analyzer_parameters, analyzer_exe_path)
    with open(json_file_path, 'r') as file:
        data = json.load(file)
        for item in data[0]['items']:
            if item['patches']:
                sys.exit(1)


    relative_path = get_relative_path(subject_project_path, java_file_path)
    java_code = read_file(java_file_path)
    original_issue_data = json.loads(read_file(json_file_path))

    for i, item in enumerate(original_issue_data[0]['items']):
        issue_data = json.dumps([{"items": [item]}], indent=4)
        diff_content = generate_diff(java_code, issue_data)
        explanation = generate_explanation(diff_content)
        modified_diff_content = replace_diff_paths(extract_diff_content(diff_content), relative_path)

        diff_file_name = f"generated_diff_{i}.diff"
        diff_file_path = os.path.join(patches_dir_path, diff_file_name)
        write_to_file(diff_file_path, modified_diff_content)

        original_issue_data[0]['items'][i]['patches'].append({
            "path": diff_file_name,
            "explanation": explanation
        })

    with open(json_file_path, 'w') as json_file:
        json.dump(original_issue_data, json_file, indent=4)

if __name__ == "__main__":
    main()
