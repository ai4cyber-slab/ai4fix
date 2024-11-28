import re
import sys

from dotenv import load_dotenv
from ai4framework.config.common_config import ConfigManager
from ai4framework.config.llm_configuration import llm_response

load_dotenv()

provider = ConfigManager._config.get('API', 'config.provider')
model = ConfigManager._config.get('API', 'config.model')
api_key = ConfigManager._config.get('API', 'config.key')

if len(sys.argv) < 4:
    print("Error: Not enough arguments provided. Expected file paths for Java code, diff, test code.")
    sys.exit(1)

java_file_path = sys.argv[1]
test_file_path = sys.argv[2]
diff_file_path = sys.argv[3]

def read_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        sys.exit(1)

java_code = read_file(java_file_path)
java_test = read_file(test_file_path)
diff_file = read_file(diff_file_path)

# prompt
prompt = f"Original Java Code:\n{java_code}\n\nDiff for the Original Java Code:\n{diff_file}\n\nTest Code for the Original Java Code:\n{java_test}\n\nPlease suggest an updated test code considering the above changes. Only write the code, no additional comment. You should return with the whole original test file with the extra modifications."
messages = [{"role": "user", "content": prompt}]
response = llm_response(provider, model, api_key, messages)

def process_response(response):
    test_code = response['message']
    
    modified_test_code = re.sub(r'class (\w+)Test', r'class \1AITest', test_code)

    return modified_test_code.replace("Updated Test Code:","")

modified_test_code = process_response(response)
print(modified_test_code)