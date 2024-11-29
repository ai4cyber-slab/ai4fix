import os
import re
import sys
import glob

from dotenv import load_dotenv, find_dotenv
from pom_modifier import PomModifier as PM
from config.llm_configuration import llm_response

class TestGenerationAI:
    def __init__(self, config=None):
        self.config = config
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        self.provider = self.config.get('API', 'config.provider')
        self.model = self.config.get('API', 'config.model')
        self.api_key = self.config.get('API', 'config.key', fallback='')
        if self.api_key == '':
            print("API key not found. Please set it in the configuration.")
            sys.exit(1)
    

    def read_file_content(self, file_path):
        """Read the content of a file and return it."""
        with open(file_path, 'r') as file:
            content = file.read()
        return content
    
    def extract_code_from_response(self, response_content):
        match = re.search(r'```java(.*?)```', response_content, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            return response_content.strip()
    
    def generate_test_class(self, java_class_path):
        prompt = f"""
        You are a highly accurate coding assistant. You are provided with the following:

        1. You are tasked with creating a JUnit 5 test class (only includes minimal test case implementations) for the following Java class below:
        ```java
        {self.read_file_content(java_class_path)}
        ```
        Please include the appropriate imports, do not use mockito just simple test cases that can be created
        by things the java already have built in and ensure the tests follows proper JUnit conventions and do not
        provide any comments or explination just the test class code and if the original java class contains private fields and params use reflection.
        """

        messages = [{"role": "user", "content": prompt}]
        response = llm_response(self.provider, self.model, self.api_key, messages)
        return self.extract_code_from_response(response['message'])
    

    def construct_test_file_path(self, source_file_path, project_path):
        normalized_path = os.path.normpath(source_file_path)
        normalized_path = normalized_path.replace(os.sep, '/')
        test_sub_path = normalized_path.replace(r'src/main/java', r'src/test/java')
        
        test_path = os.path.join(project_path, test_sub_path)
        
        test_path = os.path.normpath(test_path)
        
        dir_name, file_name = os.path.split(test_path)
        
        base_name, extension = os.path.splitext(file_name)
        test_file_name = f"{base_name}Test{extension}"
 
        return os.path.join(dir_name, test_file_name)
    
    def write_test_to_file(self, source_file_path, content, project_path):
        """Write the generated test content to a file."""
        test_file_path = self.construct_test_file_path(source_file_path, project_path)
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, 'w') as f:
            f.write(content)
        print(f"Test file written to {test_file_path}")
        return test_file_path
    
        
    def find_relevant_diff_file(self, diffs_directory, java_file_path):
        """Find the relevant diff file based on the Java file path."""

        java_file_name = os.path.basename(java_file_path).replace('.java', '')
        
        diff_files = glob.glob(os.path.join(diffs_directory, '*.diff'))
        
        # Check each diff file for relevance
        for diff_file in diff_files:
            with open(diff_file, 'r') as file:
                content = file.read()
                if java_file_name in content:
                    return diff_file
        return None
    
    def main(self, java_class_path, project_path):
        relevant_diff_file_path = self.find_relevant_diff_file(diff_dir, java_file_path)
        diff_content = self.read_file_content(relevant_diff_file_path) if relevant_diff_file_path else ""
        content = self.generate_test_class(java_class_path, diff_content)
        source_file_path = java_class_path[java_class_path.find('src'):]
        PM.main(project_path)
        test_file_path = self.write_test_to_file(source_file_path, content, project_path)
    
def rename_aittest_files(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('AITest.java'):
                new_file_name = file.replace('.java', '.java.log')
                old_file_path = os.path.join(root, file)
                new_file_path = os.path.join(root, new_file_name)
                
                os.rename(old_file_path, new_file_path)
                print(f'Renamed: {old_file_path} to {new_file_path}')
    
    
if __name__ == '__main__':
    java_file_path = sys.argv[1]
    test_file_path = sys.argv[2]
    diff_file_path = sys.argv[3]
    project_path = java_file_path[:java_file_path.find('src')]
    project_root = project_path.rstrip(os.sep)
    diff_dir = os.path.join(project_root, 'patches')
    TestGenerationAI().main(java_file_path, project_root)
    rename_aittest_files(os.path.join(project_root, 'src', 'test'))