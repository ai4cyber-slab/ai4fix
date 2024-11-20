import os
import json

from utils.logger import logger


class JSONCombiner:
    def __init__(self, config):
        self.config = config
        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.project_name = config.get('DEFAULT', 'config.project_name')
        # self.sast_issues_path = os.path.join(self.project_path, 'sast_issues.json')
        self.sast_issues_path = self.config.get("ISSUES", "config.sast_issues_path", fallback=os.path.join(self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "sast_issues.json")))
        self.results_path = self.config.get("DEFAULT", "config.analyzer_results_path")
        self.combined_output_path = self.config.get('DEFAULT', 'config.issues_path')
        self.ai4vuln_issues_path = os.path.join(self.results_path, self.project_name, 'java', 'now', 'ai4vuln_issues.json')

    def load_json(self, file_path):
        """Loads a JSON file and returns its data."""
        with open(file_path, 'r') as file:
            return json.load(file)

    def combine_json_files(self):
        """Combines two JSON files based on the configured paths."""
        if os.path.exists(self.sast_issues_path):
            data1 = self.load_json(self.sast_issues_path)
        else:
            data1 = []
        if os.path.exists(self.ai4vuln_issues_path):
            data2 = self.load_json(self.ai4vuln_issues_path)
        else:
            data2 = []
        combined_data = data1 + data2
        return combined_data

    def save_combined_json(self, combined_data):
        """Saves the combined data to a JSON file."""
        with open(self.combined_output_path, 'w') as file:
            json.dump(combined_data, file, indent=4)
        logger.info(f"Issues added to path: '{self.combined_output_path}'.")

    def run(self):
        """Executes the process of loading, combining, and saving JSON files."""
        combined_data = self.combine_json_files()
        self.save_combined_json(combined_data)
        return self.extract_issue_counts(combined_data)
    

    def extract_issue_counts(self, data):
        issue_counts = {}
        
        for issue in data:
            name = issue.get("name")
            if name:
                if name in issue_counts:
                    issue_counts[name] += 1
                else:
                    issue_counts[name] = 1
        
        return issue_counts
