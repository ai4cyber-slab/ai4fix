import openai
import sys
import re
from dotenv import load_dotenv
import os

load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')

if len(sys.argv) < 3:
    print("Error: Not enough arguments provided. Expected file paths for Java code, test code.")
    sys.exit(1)

java_file_path = sys.argv[1]
test_file_path = sys.argv[2]

def read_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        sys.exit(1)

java_code = read_file(java_file_path)
java_test = read_file(test_file_path)

# prompt
prompt = f"Updated Java Code:\n{java_code}\n\nOriginal Test Code:\n{java_test}\n\nPlease suggest an updated test code considering the above changes. Only write the code, no additional comment. You should return with the whole original test file with the extra modifications."
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": prompt}
    ]
)

def process_response(response):
    test_code = response.choices[0].message['content']
    
    modified_test_code = re.sub(r'class (\w+)Test', r'class \1AITest', test_code)

    return modified_test_code.replace("Updated Test Code:","")

modified_test_code = process_response(response)
print(modified_test_code)