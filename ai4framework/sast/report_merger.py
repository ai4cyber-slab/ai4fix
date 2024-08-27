from utils.logger import logger
import json
import os

class ReportMerger:
    def __init__(self, config):
        self.config = config

    def merge_reports(self, *report_runners):
        logger.info("Merging reports...")
        issues = []

        try:
            for runner in report_runners:
                issues.extend(runner.parse_report())

            output_path = self.config.get("ISSUES", "config.sast_issues_path", fallback=None)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'w') as json_file:
                json.dump(issues, json_file, indent=4)

            logger.info("Reports merged successfully.")
        except Exception as e:
            logger.error(f"Failed to merge reports: {e}")