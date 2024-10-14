import os
import json
import difflib
import time
import sys
import openai
import random
import subprocess
from collections import defaultdict
from dotenv import load_dotenv, find_dotenv
import re
import argparse
import uuid

class PatchManager:
    def __init__(self, config=None):
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = openai.OpenAI()

        parser = argparse.ArgumentParser(description='Process warning')
        parser.add_argument('-j', '--java_file_path', help='Path to the Java file', required=True)
        parser.add_argument('-wid', '--warning_id', help='Warning ID', required=True)
        parser.add_argument('-pp', '--project_path', help='Path to the project', required=True)
        parser.add_argument('-dod', '--diffs_output_dir', help='Directory for diff outputs', required=True)
        parser.add_argument('-jl', '--jsons_lists', help='Path to the JSON lists file', required=True)
        parser.epilog = "Example usage: python single_warning_patch.py -j path/to/your/JavaFile.java -wid yourWarningID -pp path/to/your/project -dod path/to/diffs/output -jl path/to/json/lists"
        self.args = parser.parse_args()
        self.project_path = self.args.project_path
        self.diffs_output_dir = self.args.diffs_output_dir
        self.jsons_lists = self.args.jsons_lists
        self.json_paths = self.clean_file_paths(self.jsons_lists)

    def clean_file_paths(self, file_list_path):
        """Read and clean file paths from the list file."""
        with open(file_list_path, 'r') as f:
            paths = [line.strip() for line in f.readlines()]
        return paths

    def find_json_for_java(self, java_file_path):
        """Find the corresponding JSON file for a given Java file."""
        print(self.json_paths)
        base_name = os.path.basename(java_file_path)
        suffix = base_name + '.json'
        json_file_path = next((path for path in self.json_paths if path.endswith(suffix)), None)
        
        if json_file_path is None or not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON file corresponding to {java_file_path} not found.")
        return json_file_path

    def read_json_file(self, json_file_path):
        """Read the content of the JSON file and return it in a structured way."""
        try:
            with open(json_file_path, 'r') as f:
                json_content = json.load(f)
        except Exception as e:
            print(f"Error reading JSON file {json_file_path}: {e}")
            return None
        return json_content

    def find_warnings_by_id(self, json_content, warning_id):
        """
        Find all warnings that have the specified warning_id in the JSON content.
        
        Args:
            json_content (list): The content of the JSON file.
            warning_id (str): The warning ID to search for.

        Returns:
            list: A list of warnings matching the given ID.
        """
        matching_warnings = []
        for warning in json_content:
            if warning.get('id') == warning_id:
                matching_warnings.append(warning)

        return matching_warnings
    

    def call_openai_with_retries(self, prompt, max_retries=3):
        try:
            """Call OpenAI API with retry logic and handle keyboard interrupt."""
            retries = 0
            while retries < max_retries:
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that can fix code issues."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    return response
                except openai.APIConnectionError as e:
                    print(f"Connection error: {e}, retrying...")
                except openai.AuthenticationError as e:
                    print(f"Authentication error: {e}, retrying...")
                    return None
                except openai.Timeout as e:
                    print(f"Timeout error: {e}, retrying...")
                except openai.RateLimitError as e:
                    print(f"Rate limit exceeded: {e}, retrying after delay...")
                    time.sleep(4)
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    break
                retries += 1
                time.sleep(2 ** retries + random.uniform(0, 1))
        except Exception as e:
            sys.exit(0)


    def run_maven_test(self):
        """Run 'mvn test' command and return the result."""
        with subprocess.Popen(
            ['mvn', 'test'],
            cwd=self.project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ) as process:
            stdout, stderr = process.communicate()
            result = subprocess.CompletedProcess(args=['mvn', 'test'], returncode=process.returncode, stdout=stdout, stderr=stderr)
        return result

    def analyze_maven_output(self, result):
        """Analyze the Maven output to detect and categorize errors."""
        error_type_counts = defaultdict(int)
        returned_error_message = ""
        error_detected = False
        line_counter = 0


        for output in (result.stdout, result.stderr):
            for line in output.split("\n"):
                if "[ERROR]" in line:
                    line_counter += 1
                    if line_counter == 2:
                        split_line = line.split("] ")
                        error_message_key = split_line[2] if len(split_line) > 2 else split_line[1]
                        error_message = error_message_key

                        # Fetch full error message
                        next_line_index = output.split("\n").index(line) + 1
                        while next_line_index < len(output.split("\n")):
                            next_line = output.split("\n")[next_line_index]
                            if next_line.startswith("[ERROR]") or next_line.startswith("[INFO]"):
                                break
                            error_message += "\n" + next_line
                            next_line_index += 1

                        returned_error_message = error_message
                        error_type_counts[error_message_key] += 1
                        error_detected = True
                        break
        return error_detected, error_type_counts, returned_error_message

    def extract_code_from_response(self, response_text):
        """Extract the Java code from the AI response."""
        code_blocks = re.findall(r'```(?:java|Java)?\s*(.*?)\s*```', response_text, re.DOTALL)
        return "\n".join(code_blocks).strip() if code_blocks else response_text.strip()


    def process_warning(self, warning_id, java_file_path):
        """Process each warning, generate patches, and update JSON."""

        json_file_path = self.find_json_for_java(java_file_path)

        json_content = self.read_json_file(json_file_path)
        if json_content is None:
            print(f"Error: Could not load JSON file {json_file_path}")
            return
        
        matching_warnings = self.find_warnings_by_id(json_content, warning_id)
        
        if not matching_warnings:
            print(f"No warnings with ID {warning_id} found in {java_file_path}.")
            return
        
        for warning in matching_warnings:
            explanation = f"NEW: {warning['explanation']}"
            items = warning['items']
            
            for item in items:
                textrange = item['textRange']
                startLine = textrange['startLine']
                endLine = textrange['endLine']

                try:
                    with open(java_file_path, 'r') as f:
                        file_content = f.readlines()
                        initial_content = ''.join(file_content)
                except Exception as e:
                    print(f"Error reading file {java_file_path}: {e}")

                problematic_code = ''.join(file_content[startLine-1:endLine])
                full_class_content = ''.join(file_content)

                prompt = f"""Explanation of the issue:
                {explanation}

                Here is the full file code:
                ```java
                {full_class_content}
                ```

                The problematic code is from line {startLine} to {endLine}:
                ```java
                {problematic_code}
                ```

                Instructions:
                - Modify only the code necessary to fix the issue described.
                - Do not alter comments, whitespace, or formatting.
                - Provide the complete updated code.
                """
                response = self.call_openai_with_retries(prompt)

                if response is None:
                    print(f"Failed to get response from OpenAI. Creating backup patch.")
                    sys.exit(0)
                
                generated_code = self.extract_code_from_response(response.choices[0].message.content)
                
                try:
                    with open(java_file_path, 'w') as f:
                        f.write(generated_code)
                except Exception as e:
                    print(f"Error writing to file {java_file_path}: {e}")
                    sys.exit(0)
                
                print(f"Running 'mvn clean test' for warning ID {warning['id']}...")
                result = self.run_maven_test()
                error_detected, _, _ = self.analyze_maven_output(result)
                os.makedirs(self.diffs_output_dir, exist_ok=True)
                src_path = java_file_path[java_file_path.find("src"):] if "src" in java_file_path else ""

                if not error_detected:
                # if True:
                    print(f"Maven tests passed.")
                    diff = difflib.unified_diff(
                        initial_content.splitlines(keepends=True),
                        generated_code.splitlines(keepends=True),
                        fromfile=src_path,
                        tofile=src_path,
                        n=3
                    )
                    diff_text = ''.join(diff)

                    diff_file_name = f"{os.path.splitext(os.path.basename(java_file_path))[0]}_patch_{warning['id']}_AI_{uuid.uuid4()}.diff"
                    diff_file_path = os.path.join(self.diffs_output_dir, diff_file_name)
                    try:
                        with open(diff_file_path, 'w') as diff_file:
                            diff_file.write(diff_text)
                    except Exception as e:
                        print(f"Error writing diff to file {diff_file_path}: {e}")


                    if 'patches' not in item:
                        item['patches'] = []
                    item['patches'].append({
                        "path": diff_file_name,
                        "explanation": explanation
                    })

                    try:
                        with open(json_file_path, 'w') as json_file:
                            json.dump(json_content, json_file, indent=2)
                        print(f"Updated JSON file saved at {json_file_path}.")
                    except Exception as e:
                        print(f"Error saving updated JSON file {json_file_path}: {e}")
                    
                try:
                    with open(java_file_path, 'w') as f:
                        f.write(initial_content)
                        print(f"Reverted {java_file_path} to its initial content.")
                except Exception as e:
                    print(f"Error restoring original content to {java_file_path}: {e}")

    

    def main(self):
        self.process_warning(str(self.args.warning_id), self.args.java_file_path)


if __name__ == '__main__':
    pm = PatchManager()
    pm.main()