import subprocess
import os
import sys
import json
import uuid
from utils.logger import logger

class TrivyRunner:
    """
    A class to run Trivy security scans and process the results.

    This class provides methods to execute Trivy scans, retrieve the scan reports,
    and parse the results into a structured format.
    """

    def __init__(self, config):
        """
        Initialize the TrivyRunner with configuration settings.

        Args:
            config: A configuration object containing necessary settings for Trivy.
        """
        self.config = config

    def run(self):
        """
        Execute a Trivy filesystem scan on the specified project path.

        This method constructs the Trivy command using configuration settings,
        runs the scan, and saves the output to a JSON file. If the scan fails,
        it logs an error and exits the program.
        """
        command = (
            f"{self.config.get('DEFAULT', 'config.trivy_bin')} fs "
            f"{self.config.get('DEFAULT', 'config.project_path')} "
            f"--format json "
            f"-o {self.config.get('REPORT', 'config.trivy_report_path')}"
        )     

        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Trivy scan failed: {result.stderr}")
            sys.exit(result.returncode)

    def get_report(self):
        """
        Retrieve the contents of the Trivy scan report.

        Returns:
            str: The contents of the report file if it exists, None otherwise.
        """
        report_path = self.config.get('REPORT', 'config.trivy_report_path')
        if os.path.exists(report_path):
            with open(report_path, 'r') as file:
                return file.read()
        return None

    def parse_report(self):
        """
        Parse the Trivy scan report and extract relevant vulnerability information.

        This method reads the JSON report, processes each vulnerability found,
        and structures the data into a list of issue dictionaries.

        Returns:
            list: A list of dictionaries, each representing a vulnerability issue.
        """
        report_content = self.get_report()
        if not report_content:
            logger.debug("No report found to parse.")
            return []

        issues = []
        report_data = json.loads(report_content)

        for result in report_data.get('Results', []):
            file_name = result.get('Target')

            for vulnerability in result.get('Vulnerabilities', []):
                cwe_ids = vulnerability.get('CweIDs')
                cwe_id = cwe_ids[0] if cwe_ids and len(cwe_ids) > 0 else "CWE-XXXX"
                issue = {
                    "id": str(uuid.uuid4().int)[:5],
                    "name": vulnerability.get('Title', 'Unknown'),
                    "explanation": vulnerability.get('Description', 'No description available').strip(),
                    "tags": cwe_id,
                    "items": [
                        {
                            "patches": [],
                            "textrange": {
                                "file": file_name,
                                "startLine": None,
                                "endLine": None,
                                "startColumn": None,
                                "endColumn": None
                            }
                        }
                    ]
                }
                issues.append(issue)

        return issues