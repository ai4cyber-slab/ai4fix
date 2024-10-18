from utils.logger import logger
import json
import os

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
        self.project_path = self.config.get('DEFAULT', 'config.project_path')

    def merge_reports(self, *report_runners, validation=False):
        """
        Merge reports from multiple SAST tools.

        This method combines the parsed reports from different SAST tools,
        aggregates the issues, and saves them to a single JSON file.

        Args:
            *report_runners: Variable number of report runner objects,
                             each with a parse_report() method.
            validation (bool): If True, use a different output path for validation.

        Raises:
            Exception: If there's an error during the merging process.
        """
        logger.info("Merging reports...")
        issues = []

        try:
            # Aggregate issues from all report runners
            for runner in report_runners:
                issues.extend(runner.parse_report())

            # Determine the output path based on validation flag
            if validation:
                output_path = os.path.join(self.config.get("ISSUES", "config.issues_path").replace("issues.json", "sast_validation_issues.json"))
            else:
                output_path = self.config.get("ISSUES", "config.sast_issues_path", fallback=os.path.join(self.config.get("ISSUES", "config.issues_path").replace("issues.json", "sast_issues.json")))

            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write the merged issues to a JSON file
            with open(output_path, 'w') as json_file:
                json.dump(issues, json_file, indent=4)

            logger.info("Reports merged successfully.")
        except Exception as e:
            logger.error(f"Failed to merge reports: {e}")