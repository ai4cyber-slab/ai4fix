import json
import re

def find_methods(lines):
    methods = []
    current_method_name = None
    method_start = None
    brace_count = 0

    method_pattern = re.compile(
        r'^\s*(public|private|protected)\s*'
        r'(<[^>]*>)?\s*'
        r'(abstract|default|static|synchronized|final|native|transient)?\s*'
        r'(\w+(\.\w+)?(\s*<[^>]*>)?(\s*\[[^\]]*\])?)\s+'
        r'(\w+(\.\w+)*)\s*\([^)]*\)\s*(throws\s+\w+(\s*,\s*\w+)*)?\s*{'
    )

    for line_number, line_content in lines.items():
        line_num = int(line_number.split(":")[1])


        if method_pattern.match(line_content):
            current_method_name = line_content.strip().split()[2] 
            method_start = line_num
            brace_count = 0


        brace_count += line_content.count('{')
        brace_count -= line_content.count('}')


        if current_method_name and brace_count == 0:
            methods.append((current_method_name, method_start, line_num))
            current_method_name = None
            method_start = None

    return methods

def line_belongs_to_method(line_to_check_start, line_to_check_end, methods):
    for method_name, start_line, end_line in methods:
        if start_line <= line_to_check_start <= end_line and start_line <= line_to_check_end <= end_line and line_to_check_start <= line_to_check_end:
            return True, (method_name, start_line, end_line)
    return False, None

def get_method_info_if_any(json_data, line_to_check_start, line_to_check_end):


    lines = json.loads(json_data)

    methods = find_methods(lines)

    belongs, method_info = line_belongs_to_method(line_to_check_start, line_to_check_end, methods)

    if belongs:
        method_name, start_line, end_line = method_info
        return [f"If needed Remove the entire method: {method_name}, that starts from Line:{start_line} and add the updated one.", start_line, end_line]
    else:
        return ["", None, None]

if __name__ == "__main__":
    get_method_info_if_any()