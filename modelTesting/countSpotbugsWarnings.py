import xml.etree.ElementTree as ET

file_path = 'path_to_spotbugs/spotbugsXml.xml'

def count_sast_warnings_from_file(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        warning_types = {}

        for bug in root.findall('BugInstance'):
            warning_type = bug.get('type')
            if warning_type in warning_types:
                warning_types[warning_type] += 1
            else:
                warning_types[warning_type] = 1

        total_warnings = sum(warning_types.values())

        unique_warning_types = len(warning_types)

        return total_warnings, unique_warning_types, warning_types

    except FileNotFoundError:
        return "Error: The file was not found."
    except ET.ParseError:
        return "Error: The XML is not well-formed."


result = count_sast_warnings_from_file(file_path)
print(f"Total Warnings: {result[0]},\nUnique Warning Types: {result[1]},\n")
#print(f'Warning Types: {result[2]}')
