import os
import re
import javalang
from extract_diff_methods import *

def splitter(diff):
    """
    Extract the class name from a git diff header.

    Args:
        diff (str): The git diff content.

    Returns:
        str: The extracted class name without the .java extension.
    """
    return diff.split('\n')[0].replace('diff --git a/', '').split(' ')[0].split('/')[-1].replace('.java', '')


def find_method_calls(repo_path, diff_data):
    """
    Find method calls in the repository that match the given class and methods.

    Args:
        repo_path (str): The path to the repository.
        diff_data (dict): A dictionary containing 'class' and 'methods' keys.

    Returns:
        str: The content of files containing matching method calls.
    """
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


def remove_unnecessary_diff(repo_path, diff_content):
    """
    Determine if a diff is unnecessary based on certain criteria.

    Args:
        repo_path (str): The path to the repository.
        diff_content (str): The content of the git diff.

    Returns:
        bool: True if the diff is unnecessary, False otherwise.
    """
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


def parse_diff_type(line):
    """
    Extract the interface declaration from a line of Java code.

    Args:
        line (str): A line of Java code.

    Returns:
        list or None: A list of matches if an interface declaration is found, None otherwise.
    """
    regex = r'\b(public|private|protected)?\s*interface\s+(\w+)(extends\s+\w+(\s*,\s*\w+)*)?\s*\{?'
    matches = re.findall(regex, line)
    if len(matches) > 0:
        return matches
    return None


def find_method_containing_added_line(diff_lines, index):
    """
    Find the method containing an added line in a diff.

    Args:
        diff_lines (list): A list of lines from the diff.
        index (int): The index of the added line.

    Returns:
        list or None: The parsed diff type if found, None otherwise.
    """
    # Search backwards
    while index >= 0:
        line = diff_lines[index]
        if parse_diff_type(line) != None:
            return parse_diff_type(line)
        index -= 1
    return None
