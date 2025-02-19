import os
import json
import re
from utils.logger import logger


class JSONCombiner:
    def __init__(self, config, single_file=None, skip_patches=None, external_json=None):
        self.config = config
        self.single_file = single_file
        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.project_name = config.get('DEFAULT', 'config.project_name')
        self.skip_patches = skip_patches
        self.external_json = external_json
        if self.external_json and self.skip_patches:
            self.sast_issues_path = self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "sast_issues.json")
        elif self.external_json:
            self.sast_issues_path = os.path.join(os.environ.get('PROJECT_PATH'), 'output.json')
        else:
            self.sast_issues_path = self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "sast_issues.json")
        self.results_path = self.config.get("DEFAULT", "config.analyzer_results_path")
        self.combined_output_path = self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "single_rerun_issues.json") if self.single_file else self.config.get('DEFAULT', 'config.issues_path')
        self.ai4vuln_issues_path = os.path.join(self.results_path, self.project_name, 'java', 'now', 'ai4vuln_issues.json')
        #### to be refatored ####
        if self.single_file:
            match = re.search(r"(/tmp/patch_[^/]+?)/", self.single_file)
            if match:
                temp_dir = match.group(1)
                self.results_path = self.results_path.replace(os.environ.get("PROJECT_PATH"), temp_dir)
                self.ai4vuln_issues_path = os.path.join(self.results_path, 'SE_PROJ', 'java', 'now', 'ai4vuln_issues.json')

        #######################
        # self.issue_type_exclusion = [x.strip() for x in self.config.get("DEFAULT", "config.issue_type_exclusion", fallback="").split(",")]

    def load_json(self, file_path):
        """Loads a JSON file and returns its data."""
        with open(file_path, 'r') as file:
            return json.load(file)

    def combine_json_files(self, count_issues):
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
        if count_issues:
            return combined_data
        return self.filter_excluded_issues(combined_data)
        

    def filter_excluded_issues(self, data):
        """Filters out issues based on the issue_type_exclusion list."""
        # if self.issue_type_exclusion:
        #     return [issue for issue in data if issue.get("name") not in self.issue_type_exclusion]
        return data

    def save_combined_json(self, combined_data):
        """Saves the combined data to a JSON file."""
        with open(os.path.join(os.environ.get('PROJECT_PATH'), '.ai4framework', 'issues.json'), 'w') as file:
            json.dump(combined_data, file, indent=4)

    def run(self, count_issues=False):
        """
        Executes the process of loading, combining, and saving JSON files.
        If count_issues is True, it returns the count of issues without saving the combined data.
        """
        combined_data = self.combine_json_files(count_issues)
        if not count_issues:
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
