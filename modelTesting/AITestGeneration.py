import json
import openai
import difflib
import os
import re
import subprocess
from dotenv import load_dotenv, find_dotenv
from runMavenTest import run_maven_clean_test
import tempfile
from collections import defaultdict
import time
from langchain_openai import ChatOpenAI
import javalang


# Load environment variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
openai.api_key = os.getenv('OPENAI_API_KEY')

# Base directories
base_dir = r'path_to_base_directory'
test_base_dir = r'path_to_test_root'
project_root = r'path_to_project_root'
maven_executable = r'path_to_maven_executable\mvn.cmd'
git_bash_path = "path_to_git_bash/bash.exe"

model_total_duration = 0
failed_apply_diff=0
counter = 0
passed_tests_second = 0

def extract_code_from_response(response_text):
    """Extract the Java code from the AI response."""
    code_blocks = re.findall(r'```(?:java|Java)?\s*(.*?)\s*```', response_text, re.DOTALL)
    if code_blocks:
        return "\n".join(code_blocks).strip()
    return response_text.strip()

def generate_new_test_methods(new_class_code, old_test_code, diff, returned_error_message=None):
    """Generate new test methods based on the class code and the diff."""
    
    # Base prompt
    prompt = f"""
    You are a highly accurate coding assistant. You are provided with the following:

    1. The new class code that requires testing:
    ```java
    {new_class_code}
    ```

    2. The old test file code:
    ```java
    {old_test_code}
    ```

    3. The differences between the old and new class code:
    ```
    {diff}
    ```

    Please follow these instructions carefully:

    - Generate **only the new test methods** based on the changes in the diff.
    - **Do not** include the class declaration or any setup code.
    - **Do not** generate methods that already exist in the old test file.
    - Include necessary imports, setup methods, and test cases, but avoid placeholders or comments like "Implement necessary methods."
    - Only generate test methods that cover the specific changes introduced by the diff.
    - Ensure method names, parameters, and access modifiers are consistent with the provided class code.
    """

    # Add the returned error message to the prompt if it exists (second iteration)
    if returned_error_message:
        prompt += f"\n\nAdditional information: The previous attempt to generate tests resulted in the following error:\n\n{returned_error_message}\n\n"
        prompt += "Please adjust the test generation accordingly to avoid this error."

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a Java coding assistant specialized in writing JUnit tests."},
            {"role": "user", "content": prompt}
        ],
    )
    
    return extract_code_from_response(response['choices'][0]['message']['content'])

def convert_to_unix_path(file_path):
    """Convert a Windows file path to a Unix-style path for git."""
    # Remove drive letter and replace backslashes with forward slashes
    unix_path = file_path.replace('\\', '/')
    if ':' in unix_path:
        unix_path = unix_path.split(':', 1)[-1]
    return unix_path

def generate_diff(old_code, new_code, file_path):
    """Generate the diff between the old and new class codes with proper headers."""
    file_name = os.path.basename(file_path)
    old_code_lines = old_code.splitlines()
    new_code_lines = new_code.splitlines()
    diff = difflib.unified_diff(
        old_code_lines,
        new_code_lines,
        fromfile=f"{file_name}",
        tofile=f"{file_name}",
        lineterm='',
        n=3  # Number of context lines
    )
    return '\n'.join(diff)


def run_maven_test():
    """Run Maven test command and return whether it was successful."""
    global project_root, maven_executable
    result = run_maven_clean_test(maven_executable, project_root)
    print(result.stdout)
    return result.returncode == 0

def apply_diff_to_file(diff, file_path):
    """Apply the generated diff to the file at file_path using patch in git bash."""
    # Extract the directory and the file name
    file_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)

    # Create a temporary file for the diff
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.diff') as temp_diff_file:
        modified_diff = diff.replace(file_path, file_name)
        temp_diff_file.write(modified_diff)
        temp_diff_file_name = temp_diff_file.name

    try:
        # Use git bash to apply the patch
        subprocess.run(
            [git_bash_path, '-c', f'cd "{file_dir}" && patch -p0 < "{temp_diff_file_name}"'],
            check=True
        )
        print(f"Applied diff to {file_path}.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply diff to {file_path}: {e}")
        return False 
    finally:
        # Clean up the temporary diff file
        os.remove(temp_diff_file_name)

def run_git_restore(project_root):
    """Run 'git restore .' in the project_root directory."""
    try:
        subprocess.run(['git', 'restore', '.'], cwd=project_root, check=True)
        print("Ran 'git restore .' successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to run 'git restore .': {e}")

def analyze_maven_output(result):
    """Analyze the Maven output to detect and categorize errors."""
    error_type_counts = defaultdict(int)
    error_message_key = ""
    returned_error_message = ""
    error_detected = False

    line_counter = 0

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

                returned_error_message = error_message
                error_type_counts[error_message_key] += 1
                error_detected = True
                break

    return error_detected, error_type_counts, returned_error_message


def save_generated_test(test_file_name, new_test_code, status, error_reason=None):
    """Save the generated test file directly in the generated_tests directory"""
    
    generated_test_dir = os.path.join('generated_tests', 'methodTestGeneration', "gpt4o")
    
    if not os.path.exists(generated_test_dir):
        os.makedirs(generated_test_dir)
    
    # Extract the base file name and extension
    base_name, extension = os.path.splitext(os.path.basename(test_file_name))
    
    base_name_with_status = f"{base_name}_{status}"
    
    generated_test_file_path = os.path.join(generated_test_dir, base_name_with_status + extension)
    
    # If the file already exists, append a counter to the filename
    counter = 2
    while os.path.exists(generated_test_file_path):
        generated_test_file_path = os.path.join(generated_test_dir, f"{base_name_with_status}{counter}{extension}")
        counter += 1
    
    # If the test failed, prepend the error reason to the test code
    if status == "failed_first" or status == "failed_second" or status == "failed_with_import" and error_reason:
        new_test_code = f"/*failed due to: {error_reason}*/\n\n" + new_test_code
    
    # Write the generated test code to the new file
    with open(generated_test_file_path, 'w') as f:
        f.write(new_test_code)

    print(f"Generated and saved new test file: {generated_test_file_path}")


def remove_class_declaration_and_package(new_methods):
    """
    Remove class declaration, package statement, and always remove the last closing brace if a class declaration exists.
    """
    lines = new_methods.splitlines()
    cleaned_lines = []
    class_started = False

    for line in lines:
        stripped_line = line.strip()

        # Skip package statement
        if stripped_line.startswith('package '):
            continue

        # Detect class declaration and mark when the class starts
        if stripped_line.startswith('public class') or stripped_line.startswith('class'):
            class_started = True
            continue

        # Preserve all lines except the final closing brace
        cleaned_lines.append(line)

    # If the class declaration was detected, remove the last closing brace
    if class_started and cleaned_lines and cleaned_lines[-1].strip() == '}':
        cleaned_lines.pop()

    return '\n'.join(cleaned_lines)



def insert_new_methods_to_test(old_test_code, new_methods):
    """Insert new test methods and import statements into the existing test class."""
    # Parse the old test code
    tree = javalang.parse.parse(old_test_code)
    
    # Find the class declaration
    class_declaration = None
    for _, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            class_declaration = node
            break
    
    if not class_declaration:
        pass
        #raise ValueError("No class declaration found in the test file")
    
    # Clean the new methods by removing class declarations, package statements, and extra closing brace
    new_methods_cleaned = remove_class_declaration_and_package(new_methods)
    
    # Separate import statements and methods from cleaned new_methods
    imports = []
    methods = []
    for line in new_methods_cleaned.splitlines():
        if line.startswith('import '):
            imports.append(line)
        else:
            methods.append(line)

    # Add existing imports from old_test_code to the imports list
    old_imports = re.findall(r'import [^;]+;', old_test_code)
    imports.extend(old_imports)

    # Deduplicate all import statements
    imports = list(dict.fromkeys(imports))

    # Convert methods back to a single string
    new_methods_str = '\n'.join(methods)
    
    # Remove all old imports from the old_test_code
    old_test_code_without_imports = re.sub(r'import [^;]+;', '', old_test_code)

    # Identify where to insert imports (after the package declaration, if present)
    package_match = re.search(r'package [^;]+;', old_test_code_without_imports)
    if package_match:
        # Insert imports right after the package statement
        insertion_point_for_imports = package_match.end()
    else:
        # If no package statement, insert imports at the very beginning
        insertion_point_for_imports = 0

    # Add new import statements at the identified position
    code_before_imports = old_test_code_without_imports[:insertion_point_for_imports]
    if not code_before_imports.endswith('\n'):
        code_before_imports += '\n'
    new_test_code = (
        code_before_imports +
        '\n'.join(imports) + '\n' + 
        old_test_code_without_imports[insertion_point_for_imports:]
    )
    
    # Insert new methods into the class body before the closing brace
    insertion_point_for_methods = new_test_code.rfind('}')
    new_test_code = new_test_code[:insertion_point_for_methods] + new_methods_str + '\n' + new_test_code[insertion_point_for_methods:]
    
    return new_test_code



def handle_missing_class_import(error_message, test_file_path, collected_imports_file="collected_imports.txt"):
    """
    Extracts the missing class name from an error message, finds all its correct import statements from the collected_imports.txt file,
    removes incorrect import statements from the test file, and adds the correct import statements at the appropriate position.
    Returns True if any import statements were added or removed, False otherwise.
    """
    # Extract the missing class name from the error message
    match = re.search(r'cannot find symbol\s+symbol:\s+class\s+(\w+)', error_message)
    if not match:
        return False  # No missing class found in the error message
    class_name = match.group(1)

    # Find all correct import statements for the missing class
    correct_import_statements = set()
    with open(collected_imports_file, 'r') as file:
        for line in file:
            if f'{class_name};' in line:
                correct_import_statements.add(line.strip())

    if not correct_import_statements:
        print(f"Import statements for {class_name} not found in {collected_imports_file}.")
        return False  # No import statements found

    # Read the test file content
    with open(test_file_path, 'r') as file:
        lines = file.readlines()

    # Initialize variables to store updated lines and track changes
    updated_lines = []
    import_section = True  # Flag to indicate if we're still in the import section
    changes_made = False

    # Pattern to match import statements related to the missing class
    import_pattern = re.compile(rf'^import\s+.*\b{class_name}\b.*;$')

    for line in lines:
        if line.startswith("import "):
            # Check if the import is incorrect (not in correct_import_statements)
            if import_pattern.match(line.strip()):
                if line.strip() not in correct_import_statements:
                    # Skip this line to remove the incorrect import
                    changes_made = True
                    continue  # Do not add this line to updated_lines
                else:
                    # Keep the correct import
                    updated_lines.append(line)
            else:
                # Keep other imports
                updated_lines.append(line)
        else:
            if import_section and not line.strip():
                # Still in import section (empty lines allowed)
                updated_lines.append(line)
            else:
                # Exited import section
                import_section = False
                updated_lines.append(line)

    insert_position = 0
    for i, line in enumerate(updated_lines):
        if line.startswith("import "):
            insert_position = i + 1

    # Add any missing correct import statements
    existing_imports = set(
        line.strip() for line in updated_lines if line.startswith("import ")
    )
    missing_imports = correct_import_statements - existing_imports

    if missing_imports:
        # Insert missing imports
        for import_statement in sorted(missing_imports):
            updated_lines.insert(insert_position, f"{import_statement}\n")
            insert_position += 1  # Update position to maintain order
            changes_made = True

    # If no changes were made, return False
    if not changes_made:
        return False

    # Write the updated content back to the test file
    with open(test_file_path, 'w') as file:
        file.writelines(updated_lines)

    return True  # Import statements successfully added or removed




def second_iteration(new_class_code, old_test_code, diff, test_file_name, test_file_path, returned_error_message, original_test_code):
    global failed_tests_second, passed_tests_second
    run_git_restore(project_root)
    
    # Generate new test methods with error message feedback (second iteration)
    new_test_methods_retry = generate_new_test_methods(new_class_code, old_test_code, diff, returned_error_message)

    # Insert the new test methods and retry
    new_test_code_retry = insert_new_methods_to_test(old_test_code, new_test_methods_retry)

    # Save the retried test file
    with open(test_file_path, 'w') as f:
        f.write(new_test_code_retry)

    # Re-run Maven test after retry
    result_retry = run_maven_clean_test(maven_executable, project_root)
    error_detected_retry, error_counts_retry, returned_error_message_retry = analyze_maven_output(result_retry)

    if not error_detected_retry:
        print(f"Second attempt passed for {test_file_name}.")
        passed_tests_second += 1
        save_generated_test(test_file_name, new_test_code_retry, "passed_second")
    else:
        print(f"Second attempt also failed for {test_file_name}. Reverting to original test file.")
        with open(test_file_path, 'w') as f:
            f.write(original_test_code)
        failed_tests_second += 1
        save_generated_test(test_file_name, new_test_code_retry, "failed_second", returned_error_message_retry)

failed_tests_second = 0
passed_tests_second = 0
def main(json_file_path):
    global model_total_duration, failed_apply_diff, failed_tests_second, passed_tests_second
    passed_tests = 0
    failed_tests = 0
    error_categories = defaultdict(int)
    i = 0

    with open(json_file_path, 'r') as f:
        data = json.load(f)

    while i < len(data):
        entry = data[i]
        try:
            if entry["status"]:
                pass
        except KeyError:
            i = i + 1
            continue
        i += 1
        if i >= 26 and i <= 36 or "MockConfiguration.java" in entry["fileName"]:
            i = i + 1
            continue
        
        # Run 'git restore .' before processing each entry
        run_git_restore(project_root)

        file_name = entry['fileName']
        new_class_code = entry['newClassCode']

        # Full paths
        file_path = os.path.join(base_dir, *file_name.replace('/', os.sep).split(os.sep))
        if file_name.endswith(".java"):
            test_file_name = file_name[:-5] + "Test.java"
        else:
            test_file_name = file_name + "Test"

        test_file_path = os.path.join(test_base_dir, test_file_name.replace('/', os.sep))

        # Load the old test file code
        if os.path.exists(test_file_path):
            with open(test_file_path, 'r') as f:
                old_test_code = f.read()
        else:
            old_test_code = ""

        # Read the current content of the file
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                current_file_content = f.read()
        else:
            current_file_content = ""

        # Generate the diff using the current file content
        diff = generate_diff(current_file_content, new_class_code, file_path)

        print(diff)

        # Apply the diff to the original file
        if not apply_diff_to_file(diff, file_path):
            print(f"Skipping iteration for {file_name} due to diff apply failure.")
            failed_apply_diff += 1
            i = i + 1
            continue

        # Generate new test methods (first iteration)
        start_time = time.time()
        new_test_methods = generate_new_test_methods(new_class_code, old_test_code, diff)
        end_time = time.time()
        model_duration = end_time - start_time
        model_total_duration += model_duration

        # Insert the new test methods and import statements into the existing test class
        new_test_code = insert_new_methods_to_test(old_test_code, new_test_methods)

        print(new_test_methods)

        # Save the updated test file
        with open(test_file_path, 'w') as f:
            f.write(new_test_code)

        print(f"Generated and saved new test file: {test_file_path}")

        # Save the original test file content for possible rollback
        original_test_code = old_test_code

        # Run Maven tests and analyze the output
        result = run_maven_clean_test(maven_executable, project_root)
        error_detected, error_counts, returned_error_message = analyze_maven_output(result)

        # If tests passed
        if not error_detected:
            print(f"Maven tests passed for {test_file_name}.")
            passed_tests += 1
            save_generated_test(test_file_name, new_test_code, "passed_first")
        
        # If tests failed, check for "cannot find symbol" and retry
        else:
            save_generated_test(test_file_name, new_test_code, "failed_first", returned_error_message)
            for error, count in error_counts.items():
                error_categories[error] += count
            failed_tests += 1
            print(f"Maven tests failed for {test_file_name}. Checking for missing class imports.")

            # Attempt to handle the missing class import
            success = handle_missing_class_import(
                error_message=returned_error_message,
                test_file_path=test_file_path,
                collected_imports_file="collected_imports.txt"
            )

            if success:
                # Re-run Maven test after adding the imports
                with open(test_file_path) as fp:
                    new_test_code = fp.read()

                result_retry = run_maven_clean_test(maven_executable, project_root)
                error_detected_retry, error_counts_retry, returned_error_message_retry = analyze_maven_output(result_retry)
                
                if not error_detected_retry:
                    print(f"Second attempt passed for {test_file_name}.")
                    passed_tests_second += 1
                    save_generated_test(test_file_name, new_test_code, "passed_second")
                else:
                    # Proceed to second iteration if the error persists after adding the imports
                    print(f"Second attempt failed for {test_file_name} with correct imports. Proceeding to second iteration.")
                    save_generated_test(test_file_name, new_test_code, "failed_with_import", returned_error_message_retry)
                    second_iteration(   
                        new_class_code, old_test_code, diff, test_file_name,
                        test_file_path, returned_error_message_retry,
                        original_test_code
                    )
            else:
                # Proceed to second iteration if no missing class
                print(f"No missing class found. Proceeding to second iteration.")
                second_iteration(
                    new_class_code, old_test_code, diff, test_file_name, 
                    test_file_path, returned_error_message, 
                    original_test_code
                )

        # Output the current results after each iteration
        print(f"--------------------\nCurrent results: \n{passed_tests} tests passed,\n {failed_tests} tests failed.\nPassed test for the second iteration: {passed_tests_second}\nFailed test for the second iteration: {failed_tests_second}\n")
        print(f"Error categories so far: {dict(error_categories)}--------------------")
        i += 1


    # Final results
    print(f"\n\n--------------------\nFinal results: {passed_tests} tests passed, {failed_tests} tests failed.\nPassed test for the second iteration: {passed_tests_second}\nFailed test for the second iteration: {failed_tests_second}\n")
    print(f"Error categories: {dict(error_categories)}\n")
    print(f"\ncouldn't apply patch {failed_apply_diff} times.\n")
    print(f"Total duration of the test generations: {model_total_duration}\n--------------------")


if __name__ == "__main__":
    json_file_path = "path_to_spotbugs_json\\spotbugs_dangerous_vulnerable_methods.json"
    main(json_file_path)
