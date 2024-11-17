# import os
# import json
# import tempfile
# import atexit
# from utils.logger import logger
# from config.config_path_handler import *


# class ReportMerger:
#     """
#     A class to merge reports from multiple SAST tools.

#     This class provides functionality to combine the results from various
#     static analysis security testing (SAST) tools into a single report.
#     """

#     def __init__(self, config):
#         """
#         Initialize the ReportMerger with configuration settings.

#         Args:
#             config: Configuration object containing necessary settings.
#         """
#         self.config = config
#         self.project_path = path_handler(self.config)
#         self.issues_path = self.config.get("DEFAULT", "config.issues_path")

#     def extract_issue_counts(self, data):
#         issue_counts = {}
        
#         for issue in data:
#             name = issue.get("name")
#             if name:
#                 if name in issue_counts:
#                     issue_counts[name] += 1
#                 else:
#                     issue_counts[name] = 1
        
#         return issue_counts

#     def merge_reports(self, *report_runners, validation=False):
#         """
#         Merge reports from multiple SAST tools.

#         This method combines the parsed reports from different SAST tools,
#         aggregates the issues, and saves them to a single JSON file.

#         Args:
#             *report_runners: Variable number of report runner objects,
#                              each with a parse_report() method.
#             validation (bool): If True, use a different output path for validation.

#         Raises:
#             Exception: If there's an error during the merging process.
#         """
#         if not validation:
#             logger.info("Merging reports...")
#         issues = []

#         try:
#             # Aggregate issues from all report runners
#             for runner in report_runners:
#                 issues.extend(runner.parse_report())

#             # Determine the output path based on validation flag
#             if validation:
#                 output_path = os.path.join(self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "sast_validation_issues.json"))
#                 with tempfile.NamedTemporaryFile(dir=os.path.dirname(output_path), delete=False) as temp_file:
#                     output_path = temp_file.name  # Path to the temporary file
#             else:
#                 output_path = self.config.get("ISSUES", "config.sast_issues_path", fallback=os.path.join(self.config.get("DEFAULT", "config.issues_path").replace("issues.json", "sast_issues.json")))

#             # Ensure the directory exists
#             os.makedirs(os.path.dirname(output_path), exist_ok=True)

#             # Write the merged issues to a JSON file
#             with open(output_path, 'w') as json_file:
#                 json.dump(issues, json_file, indent=4)
#             if not validation:
#                 logger.info("Reports merged successfully.")
#             atexit.register(cleanup_temp_file)
#             return self.extract_issue_counts(issues)
#         except Exception as e:
#             logger.error(f"Failed to merge reports: {e}")



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
            # Aggregate issues from all report runners
            for runner in report_runners:
                issues.extend(runner.parse_report())

            if validation:
                # Only process issues directly without creating a file
                logger.info("Processing issues in memory for validation.")
                return self.extract_issue_counts(issues)
            else:
                # Determine the output path if not in validation mode
                output_path = self.config.get(
                    "ISSUES",
                    "config.sast_issues_path",
                    fallback=os.path.join(
                        os.path.dirname(self.config.get("DEFAULT", "config.issues_path")),
                        "sast_issues.json"
                    )
                )

                # Ensure the directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Write the merged issues to a JSON file
                with open(output_path, 'w') as json_file:
                    json.dump(issues, json_file, indent=4)
                
                logger.info("Reports merged successfully.")
                return self.extract_issue_counts(issues)

        except Exception as e:
            logger.error(f"Failed to merge reports: {e}")
