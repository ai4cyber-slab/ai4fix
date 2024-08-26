import subprocess
import os
import sys
import json
import uuid
from utils.logger import logger

class TrivyRunner:
    def __init__(self, config):
        self.config = config

    def run(self):
        command = (
            f"{self.config.get('DEFAULT', 'config.trivy_bin')} fs "
            f"--format json "
            f"-o {self.config.get('DEFAULT', 'config.trivy_json_file_path')} "
            f"{self.config.get('DEFAULT', 'config.project_path')}"
        )     

        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Trivy scan failed: {result.stderr}")
            sys.exit(result.returncode)

    def get_report(self):
        report_path = self.config.get('DEFAULT', 'config.trivy_json_file_path')
        if os.path.exists(report_path):
            with open(report_path, 'r') as file:
                return file.read()
        return None

    def parse_report(self):
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