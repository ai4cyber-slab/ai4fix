import json
import openai
from openai import OpenAI
import difflib
import os
import re
import subprocess
from dotenv import load_dotenv, find_dotenv
from collections import defaultdict
import javalang
from utils.logger import logger
import time

class TestGenerator:
    def __init__(self, config):
        self.config = config
        self.project_root = self.config.get('DEFAULT', 'config.project_path')
        self.json_file_path = self.config.get('ISSUES', 'config.issues_path', fallback='')
        self.diffs_path = self.config.get('DEFAULT', 'config.results_path', fallback='')
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI()

    def generate_diff(self, old_code, new_code, file_path):
        file_name = os.path.basename(file_path)
        old_code_lines = old_code.splitlines()
        new_code_lines = new_code.splitlines()
        diff = difflib.unified_diff(
            old_code_lines,
            new_code_lines,
            fromfile=f"{file_name}",
            tofile=f"{file_name}",
            lineterm='',
            n=3
        )
        return '\n'.join(diff)

    def extract_code_from_response(self, response_text):
        code_blocks = re.findall(r'```(?:java|Java)?\s*(.*?)\s*```', response_text, re.DOTALL)
        if code_blocks:
            return "\n".join(code_blocks).strip()
        return response_text.strip()

    def generate_new_test_methods(self, new_class_code, old_test_code, diff, returned_error_message=None):
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

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return self.extract_code_from_response(response.choices[0].message.content)


    def analyze_maven_output(self, result):
        """Analyze the Maven output to detect and categorize errors."""
        error_detected = False

        for line in result.stdout.split("\n"):
            if "BUILD FAILURE" in line or "[ERROR] COMPILATION ERROR :" in line:
                error_detected = True
        return error_detected
    

    def remove_class_declaration_and_package(self, new_methods):
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


    def insert_new_methods_to_test(self, old_test_code, new_methods):
        """Insert new test methods and import statements into the existing test class."""
        # if not old_test_code.strip():
        #     old_test_code = ""
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
        new_methods_cleaned = self.remove_class_declaration_and_package(new_methods)
        
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

    def main(self):
        if not openai.api_key:
            logger.warning("OPENAI_API_KEY is not set. Skipping the test generation process.")
            return

        with open(self.json_file_path, 'r') as f:
            data = json.load(f)

        entry = data[0]

        # Extract necessary information
        item = entry['items'][0]
        file_relative_path = item['textrange']['file']
        diff_relative_path = item['patches'][0]['path']

        # Construct full paths
        file_path = os.path.join(self.project_root, file_relative_path.replace('/', os.sep))
        diff_path = os.path.join(self.diffs_path, diff_relative_path.replace('/', os.sep))

        # Read the content of the source file
        with open(file_path, 'r') as f:
            source_file_content = f.read()

        # Read the content of the diff file
        with open(diff_path, 'r') as f:
            diff_content = f.read()

        # Determine the test file path
        test_file_relative_path = file_relative_path.replace('/main/', '/test/').replace('.java', 'Test.java')
        test_file_path = os.path.join(self.project_root, test_file_relative_path.replace('/', os.sep))

        # Load the old test file code
        if os.path.exists(test_file_path):
            with open(test_file_path, 'r') as f:
                old_test_code = f.read()
        else:
            old_test_code = ""
        logger.info(f"Test Generation Started ...\n")
        start_time = time.time()
        # Generate new test methods using the AI model
        new_test_methods = self.generate_new_test_methods(source_file_content, old_test_code, diff_content)

        # Insert the new test methods into the existing test class
        new_test_code = self.insert_new_methods_to_test(old_test_code, new_test_methods)

        # Save the updated test file
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)

        try:
            with open(test_file_path, 'w') as f:
                f.write(new_test_code)
        except Exception as e:
            logger.error(f"Error writing file: {test_file_path}")
            return

        logger.info(f"Generated and saved new test file: {test_file_path}")

        # Run Maven tests and analyze the output
        result = self.run_maven_clean_test()
        error_detected = self.analyze_maven_output(result)

        # If tests passed, overwrite the test file
        if not error_detected:
            logger.info(f"Maven tests passed for {test_file_relative_path}.")
        else:
            logger.error(f"Maven tests failed for {test_file_relative_path}.")
            if old_test_code:
                with open(test_file_path, 'w') as f:
                    f.write(old_test_code)
                logger.info(f"Reverted changes to {test_file_path}.")
            else:
                # If there was no original test file, remove the newly created test file
                os.remove(test_file_path)
                logger.warn(f"Removed newly created test file: {test_file_path}.")

        # Calculate total time elapsed for test generation
        total_time_elapsed = time.time() - start_time
        logger.info(f"Test generation completed in {total_time_elapsed:.2f} seconds\n")

    def run_maven_clean_test(self):
        """Run 'mvn clean test' command and return the result."""
        result = subprocess.run(
            ['mvn', 'clean', 'test'],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        return result