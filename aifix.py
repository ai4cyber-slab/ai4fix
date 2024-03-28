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
    main_explanation = issue_data_dict['explanation']
    text_range = issue_data_dict['items'][0]['textRange']
    start_line = text_range['startLine']
    end_line = text_range['endLine']

    relevant_lines = java_code.split('\n')[start_line-1:end_line]
    relevant_code = '\n'.join(relevant_lines)

    prompt = (
        f"I have a Java file, and I need to generate a diff for a specific issue. "
        f"The issue is in the following lines (lines {start_line} to {end_line}):\n\n"
        f"Relevant code: {relevant_code}\n\n"
        f"Here's the full Java file so you know which lines need to be changed to create a full diff file: {java_code}\n\n"
        f"The main issue explanation: {main_explanation}\n"
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

def process_file(java_file_path, json_file_path, patches_dir_path, subject_project_path, start_diff_index=0):
    relative_path = get_relative_path(subject_project_path, java_file_path)
    java_code = read_file(java_file_path)
    original_issue_data = json.loads(read_file(json_file_path))

    processed_items_count = 0

    for issue in original_issue_data:
        for i, item in enumerate(issue['items']):
            if 'patches' not in item:
                item['patches'] = []

            issue_data_with_explanation = json.dumps({
                "explanation": issue.get('explanation', ''),  # Include explanation if available
                "items": [item]
            }, indent=4)

            diff_content = generate_diff(java_code, issue_data_with_explanation)
            explanation = generate_explanation(diff_content)
            modified_diff_content = replace_diff_paths(extract_diff_content(diff_content), relative_path)

            diff_file_name = f"generated_diff_{i + start_diff_index}.diff"
            diff_file_path = os.path.join(patches_dir_path, diff_file_name)
            write_to_file(diff_file_path, modified_diff_content)

            item['patches'].append({
                "path": diff_file_name,
                "explanation": explanation
            })

            processed_items_count += 1

    with open(json_file_path, 'w') as json_file:
        json.dump(original_issue_data, json_file, indent=4)

    return processed_items_count

def find_java_file(base_path, java_file_name):
    for root, dirs, files in os.walk(base_path):
        if java_file_name in files:
            return os.path.join(root, java_file_name)
    return None

def main():
    if len(sys.argv) < 7:
        sys.exit(1)

    java_file_path = sys.argv[1]
    json_file_paths = sys.argv[2].split(",")
    patches_dir_path = sys.argv[3]
    subject_project_path = sys.argv[4]
    analyzer_parameters = sys.argv[5]
    analyzer_exe_path = sys.argv[6]

    diff_index = 0

    if java_file_path and java_file_path.strip() != "":
        # Single file processing
        analyzer_parameters_with_file = analyzer_parameters + " -cu=" + java_file_path
        run_command(analyzer_parameters_with_file, analyzer_exe_path)

        for json_file_path in json_file_paths:
            processed_items = process_file(java_file_path, json_file_path, patches_dir_path, subject_project_path, diff_index)
            diff_index += processed_items
    else:
        # Multiple file processing
        run_command(analyzer_parameters, analyzer_exe_path)

        for json_file_path in json_file_paths:
            java_file_basename = os.path.splitext(os.path.basename(json_file_path))[0]
            java_file = find_java_file(subject_project_path, java_file_basename)

            if java_file is None:
                print(f"Java file {java_file_basename} not found in project path.")
                continue

            with open(json_file_path, 'r') as file:
                issues_data = json.load(file)

            for issue in issues_data:
                processed_items = process_file(java_file, json_file_path, patches_dir_path, subject_project_path, diff_index)
                diff_index += processed_items

if __name__ == "__main__":
    main()

# retrieval augmented generation
# RAG --> nagyobb kontextus
# példa repora classify
# open search (hugging face) modellek kipróbálása
# lokálisan futtatható modelleket találni kb 2 oldalnyi anyag