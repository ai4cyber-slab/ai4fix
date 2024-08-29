import re


def splitter(diff):
    return diff.split('\n')[0].replace('diff --git a/', '').split(' ')[0].split('/')[-1].replace('.java', '')


# Extract method names
def parse_diff_file(diff_content):
    diff_methods = set()
    
    # Split diff content into lines
    diff_lines = diff_content.split('\n')

    # Iterate through diff lines
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]
        if line.startswith('+') or line.startswith('-'):
            # Modified line
            if parse_method_names(line) != None:
                diff_methods.update(parse_method_names(line))
            else:
                # Check if modified line is within a method
                method_name = find_method_containing_modified_line(diff_lines, i)
                if method_name:
                    diff_methods.add(method_name)
        i += 1

    return diff_methods


# Extract method name from a line of Java code
def parse_method_names(line):
    # Example: -public void methodName(Type arg1, Type arg2) {
    method_regex = r'\b(public|private|protected)\s+(static\s+)?\b\w+\s+(\w+)\s*\(.*?\)\s*(?:throws\s+\w+(?:\s*,\s*\w+)*\s+)?\{?'
    matches = re.findall(method_regex, line)
    if len(matches) > 0:
        return matches[0][-1]
    return None


# Find the method containing the modified line
def find_method_containing_modified_line(diff_lines, index):
    # Search backwards for method declaration
    while index >= 0:
        line = diff_lines[index]
        if parse_method_names(line) != None:
            # Extract method name from the declaration
            return parse_method_names(line)
        index -= 1
    return None


def diff_methods(diff_content):
    methods = {'class': '', 'methods': []}

    method_names = parse_diff_file(diff_content)
    if method_names:
        methods['class'] = splitter(diff_content)
        methods['methods'] = method_names
    
    return methods
