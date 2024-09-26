import json
import os
from utils.logger import logger

class JSONProcessor:
    @staticmethod
    def extract_and_clean_json(input_file, output_file, base_path='/user_project'):
        """
        Extracts issues from an input JSON file, cleans and merges them, and saves to an output file.

        Args:
            input_file (str): Path to the input JSON file.
            output_file (str): Path where the cleaned JSON will be saved.
            base_path (str): The base directory from which to make file paths relative.

        Returns:
            None: This method doesn't return anything as it writes the result to a file.
        """
        def extract_issues(json_file):
            """
            Extracts and merges issues from a JSON file, converting file paths to relative paths.

            Args:
                json_file (str): Path to the JSON file to process.

            Returns:
                list: A list of merged issues. If the file is empty or contains no valid issues,
                      an empty list will be returned.
            """
            with open(json_file, 'r') as infile:
                data = json.load(infile)

            merged_issues = {}

            def make_relative_path(full_path, base):
                return os.path.relpath(full_path, base)

            for issue in data:
                explanation = issue['explanation']

                for item in issue['items']:
                    # Convert textrange file paths to relative paths
                    if 'textrange' in item and 'file' in item['textrange']:
                        item['textrange']['file'] = make_relative_path(item['textrange']['file'], base_path)
                    
                    # Remove the 'trace' key entirely
                    if 'trace' in item:
                        del item['trace']

                # Merge issues based on the explanation
                if explanation not in merged_issues:
                    merged_issues[explanation] = {
                        "id": issue["id"],
                        "name": issue["name"],
                        "explanation": explanation,
                        "tags": issue["tags"],
                        "items": issue["items"]
                    }
                else:
                    merged_issues[explanation]["items"].extend(issue["items"])

            merged_issues_list = list(merged_issues.values())
            return merged_issues_list
        
        issues = extract_issues(input_file)
        
        with open(output_file, 'w') as file:
            json.dump(issues, file, indent=4)
        
        logger.info(f"Extracted and cleaned JSON saved to {output_file}")