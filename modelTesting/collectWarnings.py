import json
import os
import xml.etree.ElementTree as ET

output_file = r"path_to_spotbugs_json\spotbugs_dangerous_vulnerable_methods.json"
xml_file_path = r'path_to_spotbugs\spotbugsXml.xml'
base_dir = "path_to_base_directory/"


def extract_code_snippet(file_path, start_line, end_line):
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
            if start_line == end_line or end_line == (start_line + 1):
                snippet = ''.join(lines[max(0, start_line - 1 - 3):min(len(lines), end_line + 3)])
            else:
                snippet = ''.join(lines[start_line - 1:end_line])
        return snippet
    except Exception as e:
        print(f"Error reading file: {e}")
        return f"Error reading file: {e}"

def extract_class_code(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
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

def parse_spotbugs_xml(xml_file_path):
    global base_dir
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    

    bugs = []
    for bug_instance in root.findall("BugInstance"):
        abbrev = bug_instance.get("abbrev")
        warning_type = bug_instance.get("type")
        long_message = bug_instance.find("LongMessage").text.strip()

        # Function to safely get line numbers
        def get_line_numbers(element):
            start = element.get("start")
            end = element.get("end")
            if start is not None and end is not None:
                return int(start), int(end)
            return None, None

        method_line = bug_instance.find("Method/SourceLine")
        if method_line is not None:
            start_line_number, end_line_number = get_line_numbers(method_line)
            start_line_number = start_line_number - 1
            end_line_number = end_line_number + 1
            source_path = method_line.get("sourcepath")
        """else:
            class_line = bug_instance.find("Class/SourceLine")
            if class_line is not None:
                start_line_number, end_line_number = get_line_numbers(class_line)
                source_path = class_line.get("sourcepath")
            else:
                general_line = bug_instance.find("SourceLine")
                if general_line is not None:
                    start_line_number, end_line_number = get_line_numbers(general_line)
                    source_path = general_line.get("sourcepath")
                else:
                    continue"""

        if start_line_number is None or end_line_number is None or source_path is None:
            continue

        file_path = find_file(base_dir, source_path)
        if file_path:
            code_snippet = extract_code_snippet(file_path, start_line_number, end_line_number)
            class_code = extract_class_code(file_path)
            bugs.append({
                "explanation": long_message,
                "fileName": source_path,
                "startLineNumber": start_line_number+1,
                "endLineNumber": end_line_number-1,
                "codeSnippet": code_snippet,
                #"classCode": class_code,
                #"warningType": warning_type
            })
    return bugs

vulnerabilities = parse_spotbugs_xml(xml_file_path)

# Save the results as JSON
with open(output_file, "w") as json_file:
    json.dump(vulnerabilities, json_file, indent=4)

print(f"JSON output saved to {output_file}")
