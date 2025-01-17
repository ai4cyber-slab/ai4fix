import os
import re
import time
import random
from config.llm_configuration import llm_response
from utils.logger import logger
from generation.build_dependencies_modifier import BuildDependenciesModifier


CREATE_PROMPT = """
You are a helpful assistant tasked with generating test files for Java classes in Junit. I will provide you with the before and after states of a Java file in JSON format to highlight the changes made. Your goal is to create a complete Java test file focusing only on the parts of the code that were changed. Each test method you generate should validate the updated functionality or behavior introduced by the changes.

Here is the JSON structure of changes made to a Java file:
Before:
```json
{0}
```
After:
```json
{1}
```
Using this example, create a test file in Java. The test file should include:

Explicit imports for all required dependencies don't assume pre existance of anything be careful with the imports.
Each test uses explicit imports within the code instead of assuming global imports.
the fully qualified path to the class/method being tested is `{2}`.
A utility method getFieldValue is included for reflective access to private fields for validation.
A test class with this descriptive name (e.g., `{3}`).
Test methods that specifically validate the updated behavior.
Minimal boilerplate, focusing on concise and effective test cases for the changes.
Return only the Java test file as your response.
"""

UPDATE_PROMPT = """
You are a software tester with over 15 years of experience tasked with updating test files for Java classes. I will provide you with the following:

1. The original content of an existing test file.
2. The diff content of the java file to highlight the changes made to it.

Your goal is to:
- Add a **new test method** to the provided test file content that validates the specific changes made to the Java file. This method must focus solely on testing the updated functionality or behavior. 
- Leave all other parts of the test file unchanged.

Here is the structure of the input:
Existing Original Test File:
```java
{0}
```
Diff:
```diff
{1}
```

Using this input, generate the updated test file content that includes:
- **Only one new test method** that validates the updated functionality or behavior based on the changes provided.
- Explicit imports for all required dependencies, using only the preexisting ones. Do not add imports for libraries not already included or not built-in.
- Maintain the fully qualified path to the class/method being tested as `{2}`.
- Ensure the test class retains its current structure and naming, such as `{3}`.

Important: If the member (constructor, field, or method) is private, always use setAccessible(true) to bypass access restrictions. 
Validate the member's modifiers with Modifier.isPrivate(), and catch all exceptions using a single catch block for ReflectiveOperationException. 
Re-throw exceptions as needed based on the use case to ensure the correct behavior."

If no changes are needed, return **NO NEED**. Otherwise, return only the fully updated Java test file as your response. **DO NOT MODIFY OR REMOVE EXISTING TEST METHODS**. **DO NOT HALLUCINATE**. Ensure the new test method is clearly aligned with the provided changes and nothing else.
"""

class TestGenerator:
    def __init__(self, project_root, config):
        self.config = config
        self.project_path = project_root
        self.build_tool = self.config.get('DEFAULT', 'config.build_tool', fallback='maven').lower()

    def extract_test_file(self, java_file_path):
        if not os.path.exists(java_file_path):
            raise Exception(f"Java file not found: {java_file_path}")
        test_file_relative_path = java_file_path.replace('/main/', '/test/').replace('.java', 'Test.java')
        test_file_path = test_file_relative_path.replace('/', os.sep)
        return test_file_path

    def generate_test(self, java_file_path, full_import, initial_section, updated_section, diff_content):
        """
        Generate or update a test file for the given Java file.
        """
        test_file_path = self.extract_test_file(java_file_path)
        test_existed_before = os.path.exists(test_file_path)
        original_content = None


        if test_existed_before:
            with open(test_file_path, 'r') as test_file:
                original_content = test_file.read()
            prompt = UPDATE_PROMPT.format(
                original_content,
                diff_content,
                full_import,
                java_file_path.split("/")[-1].replace(".java", "") + "Test"
            )
        else:
            prompt = CREATE_PROMPT.format(
                initial_section,
                updated_section,
                full_import,
                java_file_path.split("/")[-1].replace(".java", "") + "Test"
            )

        new_content = self.generate_test_file_content(prompt, self.config)
        if test_existed_before:
            with open(test_file_path, 'w') as test_file:
                test_file.write(new_content)
        else:
            os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
            try:
                with open(test_file_path, 'w') as test_file:
                    test_file.write(new_content)
            except Exception as e:
                logger.error(f"Failed to write test file: {e}")

        # TODO: maybe give option to user to create and set up his own dependencies.json file
        dependencies_json_path = self.config.get(
            'TESTS',
            'config.pom_dependencies_json_path',
            fallback=os.path.join(os.sep, 'app', 'utils', 'dependencies.json')
        )
        # self.update_build_dependencies(self.project_path, test_file_path, dependencies_json_path, self.build_tool)

        return test_file_path, test_existed_before, original_content

    def extract_code_from_response(self, response_text):
        """Extract content from any triple backtick block in the AI response."""
        content_blocks = re.findall(r'```(?:[^\s]*)?\s*(.*?)\s*```', response_text, re.DOTALL)
        return "\n".join(content_blocks).strip() if content_blocks else response_text.strip()

    def generate_test_file_content(self, prompt, config, max_retries=3):
        """
        Generate the test file content by calling the LLM with retries.
        """
        try:
            retries = 0
            while retries < max_retries:
                try:
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt},
                    ]
                    response = llm_response(
                        provider=config.get('API', 'config.provider'),
                        model=config.get('API', 'config.model'),
                        api_key=config.get('API', 'config.key'),
                        messages=messages,
                        endpoint=config.get('API', 'config.azure_endpoint'),
                        api_v=config.get('API', 'config.azure_api_version')
                    )
                    return self.extract_code_from_response(response['message'])
                except Exception as e:
                    logger.error(f"Unexpected error: {e}, retrying...")
                retries += 1
                time.sleep(2 ** retries + random.uniform(0, 1))
        except Exception as e:
            logger.error(f"AI call failed after retries: {e}")
        return None

    def update_build_dependencies(self, project_root, test_file_path, dependencies_json_path, build_tool):
        """
        Update build dependencies based on the detected build tool.
        Currently only Maven logic is implemented. For other build tools like Gradle,
        future logic can be added.
        """
        logger.info("Starting the process to update build dependencies based on Java file imports.")
        try:
            if build_tool == 'maven':
                modifier = BuildDependenciesModifier(project_root, test_file_path, dependencies_json_path, build_tool=build_tool)
                success = modifier.process_java_file(test_file_path)
                if success:
                    logger.info("Build dependencies update process completed successfully for Maven.")
                else:
                    logger.warning("No updates were necessary or issues were encountered for Maven.")
                return success
            elif build_tool == 'gradle':
                # TODO: Add Gradle
                logger.info("Gradle build tool detected.")
                return True
            else:
                logger.info(f"Build tool '{build_tool}' not recognized. No dependency updates performed.")
                return False
        except Exception as e:
            logger.error(f"An error occurred during the build dependencies update process: {str(e)}")
            return False