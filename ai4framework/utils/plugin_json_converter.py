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
        self.output_directory = os.path.join(self.input_file.replace(os.path.basename(self.input_file), 'validation'), 'jsons')
        self.json_txt_file = self.config.get('DEFAULT', 'config.jsons_listfile')


    def load_input_json(self):
        """
        Load JSON data from a file.
        """
        with open(self.input_file, 'r') as f:
            data = json.load(f)
        return data

    # def group_entries_by_file(self, entries):
    #     """
    #     Group entries by the 'file' attribute in 'textrange'.
    #     Within each file, group by 'name' (issue type) and prepare the structure with 'name' and 'items'.
    #     """
    #     grouped = defaultdict(lambda: defaultdict(list))
    #     for entry in entries:
    #         items = entry.get('items', [])
    #         name = entry.get('name')
    #         entry_id = entry.get('id')  # Get the ID from the entry
    #         explanation = entry.get('explanation')  # Get the explanation from the entry
    #         if not name:
    #             continue

    #         for item in items:
    #             textrange = item.get('textrange', {})
    #             file_path = textrange.get('file')
    #             if not file_path:
    #                 continue

    #             text_range = {
    #                 "startLine": textrange.get('startLine'),
    #                 "endLine": textrange.get('endLine'),
    #                 "startColumn": textrange.get('startColumn'),
    #                 "endColumn": textrange.get('endColumn')
    #             }

    #             patches = item.get('patches', [])

    #             # grouped[file_path][name].append({
    #             #     "patches": patches,
    #             #     "textRange": text_range
    #             # })
    #             grouped[file_path][name].append({
    #                 "id": entry_id,
    #                 "explanation": explanation,
    #                 "patches": patches,
    #                 "textRange": text_range
    #             })
    #     return grouped

    def group_entries_by_file(self, entries):
        """
        Group entries by the 'file' attribute in 'textrange'.
        Within each file, group by 'name' (issue type) and prepare the structure with 'id', 'name', 'explanation', and 'items'.
        """
        grouped = defaultdict(list)
        for entry in entries:
            items = entry.get('items', [])
            name = entry.get('name')
            entry_id = entry.get('id')  # Get the ID from the entry
            explanation = entry.get('explanation')  # Get the explanation from the entry

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

                # Append a dictionary with id, name, explanation, and items containing patches and textrange
                grouped[file_path].append({
                    "id": entry_id,
                    "name": name,
                    "explanation": explanation,
                    "items": [
                        {
                            "patches": patches,
                            "textRange": text_range
                        }
                    ]
                })
        return grouped


    # def write_grouped_json(self, grouped_data):
    #     """
    #     Write each group's data to a separate JSON file and collect their paths.
    #     Each JSON file corresponds to a single Java file and contains issues grouped by issue type.
    #     The output directory structure mirrors the original file paths.
    #     """
    #     json_file_paths = []

    #     for file_path, issues_by_type in grouped_data.items():
    #         normalized_file_path = os.path.normpath(file_path)

    #         # Create the output file path by appending .json to the normalized file path
    #         output_file_path = os.path.join(self.output_directory, normalized_file_path + '.json')

    #         # Ensure the directory exists
    #         os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    #         # Convert the grouped data into the new structure with "name" and "items"
    #         # output_json = []
    #         # for issue_type, issues in issues_by_type.items():
    #         #     output_json.append({
    #         #         "name": issue_type,
    #         #         "items": issues  # The issues themselves are the "items" under the "name"
    #         #     })
    #         output_json = []
    #         for issue_type, issues in issues_by_type.items():
    #             # Here, include the "id" and "explanation" from the grouped data
    #             output_json.append({
    #                 "name": issue_type,
    #                 "items": [
    #                     {
    #                         "id": issue.get("id"),  # Add ID
    #                         "explanation": issue.get("explanation"),  # Add Explanation
    #                         "patches": issue.get("patches"),
    #                         "textRange": issue.get("textRange")
    #                     } for issue in issues
    #                 ]
    #             })

    #         # Write the new structured JSON to a file
    #         with open(output_file_path, 'w') as f:
    #             json.dump(output_json, f, indent=2)

    #         # Collect the absolute path of the JSON file
    #         # json_file_paths.append(os.path.abspath(output_file_path))
    #         json_file_paths.append(output_file_path)


    #     return json_file_paths

    def write_grouped_json(self, grouped_data):
        """
        Write each group's data to a separate JSON file and collect their paths.
        Each JSON file corresponds to a single Java file and contains issues grouped by issue type.
        The output directory structure mirrors the original file paths.
        """
        json_file_paths = []

        for file_path, entries in grouped_data.items():
            normalized_file_path = os.path.normpath(file_path)

            # Create the output file path by appending .json to the normalized file path
            output_file_path = os.path.join(self.output_directory, normalized_file_path + '.json')

            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

            # Write the new structured JSON to a file
            with open(output_file_path, 'w') as f:
                json.dump(entries, f, indent=2)

            # Collect the absolute path of the JSON file
            json_file_paths.append(output_file_path)

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

        # Group the entries by file path and issue type
        grouped_data = self.group_entries_by_file(input_data)

        # Write the grouped JSON data to files
        json_paths = self.write_grouped_json(grouped_data)

        # Write the paths of the created JSON files to the specified text file
        self.write_json_paths(json_paths)

        logger.info(f"Processed {len(json_paths)} JSON files.")
        logger.info(f"Paths have been written to '{self.json_txt_file}'.")
