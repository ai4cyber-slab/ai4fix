import json
import os
from collections import defaultdict
from utils.logger import logger

class JsonPluginConverter:
    def __init__(self, config):
        """
        Initialize the JSONProcessor with configuration.

        Args:
            input_file (str): Path to the input JSON file.
            output_directory (str): Directory where the grouped JSON files will be stored.
            json_txt_file (str): Path to the file where the list of output JSON paths will be written.
        """
        self.config = config
        self.input_file = self.config.get('ISSUES', 'config.issues_path', fallback='')
        self.output_directory = os.path.join(self.config.get('DEFAULT', 'config.project_path'), 'patches', 'jsons')
        self.json_txt_file = self.config.get('DEFAULT', 'config.jsons_listfile')


    def load_input_json(self):
        """
        Load JSON data from a file.
        """
        with open(self.input_file, 'r') as f:
            data = json.load(f)
        return data

    def group_entries_by_file(self, entries):
        """
        Group entries by the 'file' attribute in 'textrange'.
        Within each file, group by 'name' (issue type).
        """
        grouped = defaultdict(lambda: defaultdict(list))
        for entry in entries:
            items = entry.get('items', [])
            name = entry.get('name')
            if not name:
                continue

            for item in items:
                textrange = item.get('textrange', {})
                file_path = textrange.get('file')
                if not file_path:
                    continue

                text_range = {
                    "startLine": textrange.get('startLine'),
                    "endLine": textrange.get('endLine'),
                    "startColumn": textrange.get('startColumn'),
                    "endColumn": textrange.get('endColumn')
                }

                patches = item.get('patches', [])

                grouped[file_path][name].append({
                    "patches": patches,
                    "textRange": text_range
                })
        return grouped

    def write_grouped_json(self, grouped_data):
        """
        Write each group's data to a separate JSON file and collect their paths.
        Each JSON file corresponds to a single Java file and contains issues grouped by issue type.
        The output directory structure mirrors the original file paths.
        """
        json_file_paths = []

        for file_path, issues_by_type in grouped_data.items():

            normalized_file_path = os.path.normpath(file_path)

 
            output_file_path = os.path.join(self.output_directory, normalized_file_path + '.json')

            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

            output_json = {}
            for issue_type, issues in issues_by_type.items():
                output_json[issue_type] = issues

            with open(output_file_path, 'w') as f:
                json.dump(output_json, f, indent=2)

            json_file_paths.append(os.path.abspath(output_file_path))  # Use absolute paths

        return json_file_paths

    def write_json_paths(self, json_paths):
        """
        Write all JSON file paths to a single text file.
        """
        with open(self.json_txt_file, 'w') as f:
            for path in json_paths:
                f.write(f"{path}\n")

    def process(self):
        """
        Process the input JSON file by grouping entries and writing them to separate files.
        """
        try:
            input_data = self.load_input_json()
        except FileNotFoundError:
            logger.error(f"Error: The file '{self.input_file}' does not exist.")
            return
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return

        grouped_data = self.group_entries_by_file(input_data)

        json_paths = self.write_grouped_json(grouped_data)

        self.write_json_paths(json_paths)

        logger.info(f"Processed {len(json_paths)} JSON files.")
        logger.info(f"Paths have been written to '{self.json_txt_file}'.")



