import os
import json
from utils.logger import logger

class ReportMerger:
    """
    A class to merge reports from multiple SAST tools.

    This class provides functionality to combine the results from various
    static analysis security testing (SAST) tools into a single report.
    """

    def __init__(self, config):
        """
        Initialize the ReportMerger with configuration settings.

        Args:
            config: Configuration object containing necessary settings.
        """
        self.config = config
        self.project_path = self.config.get('DEFAULT', 'config.dir_to_analyze')
        self.issues_path = self.config.get("DEFAULT", "config.issues_path")

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

    def merge_reports(self, *report_runners, validation=False):
        """
        Merge reports from multiple SAST tools.

        This method combines the parsed reports from different SAST tools,
        aggregates the issues, and optionally saves them to a JSON file.

        Args:
            *report_runners: Variable number of report runner objects,
                             each with a parse_report() method.
            validation (bool): If True, skips file creation and processes issues in memory.

        Raises:
            Exception: If there's an error during the merging process.
        """
        if not validation:
            logger.info("Merging reports...")
        issues = []

        try:
            for runner in report_runners:
                if runner is None:
                    continue
                issues.extend(runner.parse_report())

            if validation:
                logger.info("Processing issues in memory for validation.")
                return self.extract_issue_counts(issues)
            else:
                output_path = self.config.get(
                    "ISSUES",
                    "config.sast_issues_path",
                    fallback=os.path.join(
                        os.path.dirname(self.config.get("DEFAULT", "config.issues_path")),
                        "sast_issues.json"
                    )
                )
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                with open(output_path, 'w') as json_file:
                    json.dump(issues, json_file, indent=4)
                
                logger.info("Reports merged successfully.")
                return self.extract_issue_counts(issues)

        except Exception as e:
            logger.error(f"Failed to merge reports: {e}")
