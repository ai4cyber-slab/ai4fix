import json

class IssueComparer:
    def __init__(self, json1_path, json2_path, java_file_path):
        """
        Initializes the IssueComparer with paths to the JSON files and the Java file.

        Args:
            json1_path (str): Path to the first JSON file (before changes).
            json2_path (str): Path to the second JSON file (after changes).
            java_file_path (str): The path of the Java file to filter issues.
        """
        self.json1_path = json1_path
        self.json2_path = json2_path
        self.java_file_path = java_file_path
        self.issues1 = []
        self.issues2 = []
        self.removed_issue_ids = []
        self.existing_issue_ids = []

    def load_issues(self, json_data):
        """
        Loads and filters issues related to the specified Java file.

        Args:
            json_data (list): The JSON data loaded from a file.

        Returns:
            list: A list of tuples containing the comparison key and the 'id' itself.
        """
        issues = []
        for issue in json_data:
            # Extract relevant fields
            issue_name = issue.get('name', '').lower()
            issue_explanation = issue.get('explanation', '').lower()
            issue_tag = issue.get('tags', '').lower()
            # Filter issues related to the specific Java file
            for item in issue.get('items', []):
                textrange = item.get('textrange', {})
                if textrange.get('file') == self.java_file_path:
                    # Create a comparison key using 'name' and 'explanation' and 'tags'
                    comparison_key = (issue_name, issue_explanation, issue_tag)
                    issue_id = issue.get('id', '')
                    issues.append((comparison_key, issue_id))
                    break  # No need to check other items in this issue
        return issues

    def compare_issues(self):
        """
        Compares issues from the two JSON files for the specified Java file.
        Populates 'removed_issue_ids' and 'existing_issue_ids' lists.
        """
        # Load JSON data from the provided file paths
        with open(self.json1_path, 'r') as f:
            json1_data = json.load(f)

        with open(self.json2_path, 'r') as f:
            json2_data = json.load(f)

        # Load and filter issues from both JSONs
        self.issues1 = self.load_issues(json1_data)
        self.issues2 = self.load_issues(json2_data)

        # Build dictionaries for comparison
        issues1_dict = {key: issue_id for key, issue_id in self.issues1}
        issues2_keys = {key for key, _ in self.issues2}

        # Find issues present in json1 but not in json2 (removed issues)
        self.removed_issue_ids = []
        self.existing_issue_ids = []
        for key, issue_id in issues1_dict.items():
            if key not in issues2_keys:
                self.removed_issue_ids.append(issue_id)
            else:
                self.existing_issue_ids.append(issue_id)

    def get_removed_issue_ids(self):
        """
        Returns the IDs of issues that were removed (present in json1 but not in json2).

        Returns:
            list: List of removed issue IDs.
        """
        return self.removed_issue_ids

    def get_existing_issue_ids(self):
        """
        Returns the IDs of issues that still exist in json2.

        Returns:
            list: List of existing issue IDs.
        """
        return self.existing_issue_ids