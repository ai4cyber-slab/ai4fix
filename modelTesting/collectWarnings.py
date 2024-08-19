import os
import re
import xml.etree.ElementTree as ET
import json

base_dir = "path_to_base_directory/"
previous_warnings_file = r"path_to_spotbugs_json\spotbugs_dangerous_vulnerable_methods2.json"
first_json_file = r"path_to_spotbugs_json\spotbugs_dangerous_vulnerable_methods.json"
output_file = r"path_to_spotbugs_json\spotbugs_dangerous_vulnerable_methods.json"
xml_file_path = r'path_to_spotbugs\spotbugsXml.xml'

class_start_line2 = 0
class_end_line2 = 0

def extract_code_snippet(file_path, start_line, end_line):
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
            snippet = ''.join(lines[max(0, start_line - 2):min(len(lines), end_line)])
        return snippet
    except Exception as e:
        print(f"Error reading file: {e}")
        return f"Error reading file: {e}"

def generate_composite_id(warning):
    explanation = warning.get("explanation", "")
    file_name = warning.get("fileName", "")
    
    composite_id = f"{explanation}-{file_name}"
    return composite_id

def extract_class_code(file_path, start_line, hint_end_line):
    global class_start_line2, class_end_line2
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()

        class_pattern = re.compile(r'^\s*(public|protected|private)?\s*(abstract|static|final|strictfp)?\s*class\s+\w+')

        adjusted_start_line = max(0, start_line - 10)
        found_class_start = False
        for i in range(adjusted_start_line, start_line):
            if class_pattern.search(lines[i]) and not lines[i].strip().startswith("//") and "/*" not in lines[i] and "*/" not in lines[i]:
                start_line = i
                found_class_start = True
                break
        
        if not found_class_start:
            start_line = max(0, start_line - 2)

        open_braces = 0
        close_braces = 0
        class_end_line = start_line

        for i in range(start_line, len(lines)):
            line = lines[i]
            open_braces += line.count('{')
            close_braces += line.count('}')
            if open_braces > 0 and open_braces == close_braces:
                class_end_line = i + 1
                if abs(class_end_line - hint_end_line) <= 10:
                    break

        if class_end_line <= start_line:
            class_end_line = len(lines)

        class_start_line2 = start_line
        class_end_line2 = class_end_line

        class_code = ''.join(lines[start_line:class_end_line])
        return class_code

    except Exception as e:
        print(f"Error reading file: {e}")
        return f"Error reading file: {e}"

def find_file(base_dir, relative_path):
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == os.path.basename(relative_path):
                full_path = os.path.join(root, file)
                return full_path
    print(f"File not found: {relative_path}")
    return None

def parse_spotbugs_xml(xml_file_path, max_warnings=100, min_warnings_per_file=5):
    global base_dir
    tree = ET.parse(xml_file_path)
    root = tree.getroot()

    file_warnings = {}
    total_warnings = 0

    for bug_instance in root.findall("BugInstance"):
        if total_warnings >= max_warnings:
            break

        warning_type = bug_instance.get("type")
        long_message = bug_instance.find("LongMessage").text.strip()

        def get_line_numbers(element):
            start = element.get("start")
            end = element.get("end")
            if start is not None and end is not None:
                return int(start), int(end)
            return None, None

        method_start_line = method_end_line = class_start_line = class_end_line = None
        method_source_path = class_source_path = None

        method_line = bug_instance.find("Method/SourceLine")
        if method_line is not None:
            method_start_line, method_end_line = get_line_numbers(method_line)
            method_source_path = method_line.get("sourcepath")

        class_line = bug_instance.find("Class/SourceLine")
        if class_line is not None:
            class_start_line, class_end_line = get_line_numbers(class_line)
            class_source_path = class_line.get("sourcepath")

        if method_start_line is None or method_end_line is None or method_source_path is None:
            if class_start_line is None or class_end_line is None or class_source_path is None:
                continue

        source_path = method_source_path if method_source_path else class_source_path
        start_line_number = method_start_line if method_start_line else class_start_line
        end_line_number = method_end_line if method_end_line else class_end_line

        file_path = find_file(base_dir, source_path)
        if file_path:
            local_class_start_line2 = class_start_line
            local_class_end_line2 = class_end_line

            code_snippet = extract_code_snippet(file_path, start_line_number, end_line_number)
            class_code = extract_class_code(file_path, local_class_start_line2, local_class_end_line2)

            # Calculate class size
            class_size = len(class_code.splitlines())

            # Only keep classes between 30 and 300 lines
            if class_size < 30 or class_size > 300:
                continue

            warning_data = {
                "explanation": long_message,
                "fileName": source_path,
                "methodStartLineNumber": start_line_number - 1,
                "methodEndLineNumber": end_line_number + 1,
                "warning_type": warning_type,
                "codeSnippet": code_snippet,
                "classStartLineNumber": class_start_line2 + 1,
                "classEndLineNumber": class_end_line2,
                "classCode": class_code,
                "compositeId": generate_composite_id({
                    "explanation": long_message,
                    "fileName": source_path,
                }),
                "classSize": class_size
            }

            if source_path not in file_warnings:
                file_warnings[source_path] = []

            file_warnings[source_path].append(warning_data)

    final_warnings = []
    for source_path, warnings in file_warnings.items():
        if len(warnings) > min_warnings_per_file:
            final_warnings.extend(warnings)
            total_warnings += len(warnings)
        if total_warnings >= max_warnings:
            break

    return final_warnings[:max_warnings]

def update_existing_warnings(previous_warnings, current_warnings):
    current_warnings_dict = {w["compositeId"]: w for w in current_warnings}
    updated_warnings = []

    for warning in previous_warnings:
        composite_id = warning.get("compositeId")
        if composite_id in current_warnings_dict:
            updated_warnings.append(current_warnings_dict[composite_id])
        else:
            updated_warnings.append({})

    return updated_warnings

def initialize_json_with_warnings(current_warnings):
    return current_warnings

def filter_and_sort_vulnerabilities(vulnerabilities):
    # Filter out vulnerabilities with errors in the class code
    filtered_vulnerabilities = [
        v for v in vulnerabilities 
        if "Error reading file" not in v.get("classCode", "")
    ]
    
    # Sort the vulnerabilities by the size of the class
    sorted_vulnerabilities = sorted(
        filtered_vulnerabilities, 
        key=lambda v: v["classSize"]
    )
    
    return sorted_vulnerabilities

# Load previous warnings if the file exists
if os.path.exists(previous_warnings_file):
    with open(previous_warnings_file, 'r') as json_file:
        try:
            previous_warnings = json.load(json_file)
        except json.JSONDecodeError:
            previous_warnings = []
else:
    previous_warnings = []

# Parse current XML to get warnings (limit to 100)
current_warnings = parse_spotbugs_xml(xml_file_path, max_warnings=100)

if not previous_warnings:
    final_warnings = initialize_json_with_warnings(current_warnings)
    
    with open(previous_warnings_file, "w") as json_file:
        json.dump(final_warnings, json_file, indent=4)
else:
    final_warnings = update_existing_warnings(previous_warnings, current_warnings)

with open(output_file, "w") as json_file:
    json.dump(final_warnings, json_file, indent=4)

print(f"JSON output saved to {output_file}")
print(f"Second JSON file also updated: {previous_warnings_file}")