import os
import re
import javalang
from extract_diff_methods import *


def splitter(diff):
    return diff.split('\n')[0].replace('diff --git a/', '').split(' ')[0].split('/')[-1].replace('.java', '')


def find_method_calls(repo_path, diff_data):
    class_name = diff_data['class']
    method_names = diff_data['methods']
    method_calls = ''

    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    try:
                        tree = javalang.parse.parse(content)
                    except javalang.parser.JavaSyntaxError:
                            continue

                    instances = set()

                    for path, node in tree:
                        if isinstance(node, javalang.tree.VariableDeclarator):
                            if isinstance(node.initializer, javalang.tree.ClassCreator):
                                if node.initializer.type.name == class_name:
                                    instances.add(node.name)

                        if isinstance(node, javalang.tree.MethodInvocation):
                            if node.qualifier in instances or node.qualifier == class_name:
                                if node.member in method_names:
                                    method_calls += content

    return method_calls


# Parse diff file and extract changes
def remove_unnecessary_diff(repo_path, diff_content):

    class_name = splitter(diff_content)
    if 'Test' in class_name:
        return True
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    try:
                        tree = javalang.parse.parse(content)
                    except javalang.parser.JavaSyntaxError:
                            continue
        
                    for path, node in tree.filter(javalang.tree.TypeDeclaration):
                        if isinstance(node, javalang.tree.InterfaceDeclaration) and node.name == class_name:
                            return True

    return False


# Extract diff type from a line of Java code
def parse_diff_type(line):
    regex = r'\b(public|private|protected)?\s*interface\s+(\w+)(extends\s+\w+(\s*,\s*\w+)*)?\s*\{?'
    matches = re.findall(regex, line)
    if len(matches) > 0:
        return matches
    return None


def find_method_containing_added_line(diff_lines, index):
    # Search backwards
    while index >= 0:
        line = diff_lines[index]
        if parse_diff_type(line) != None:
            return parse_diff_type(line)
        index -= 1
    return None
