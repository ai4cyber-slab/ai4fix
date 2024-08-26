import subprocess
import os
import sys
import xml.etree.ElementTree as ET
import uuid
from utils.logger import logger

class PMDRunner:
    def __init__(self, config):
        self.config = config

    def run(self, java_files):

        command = (
                f"{self.config.get('DEFAULT', 'config.pmd_bin')} check "
                f"-d {','.join(java_files)} "
                f"-R {self.config.get('DEFAULT', 'config.pmd_ruleset')} "
                f"-f xml "
                f"-r {self.config.get('DEFAULT', 'config.pmd_xml_file_path')} "
                "--no-fail-on-violation "
            )


        result = subprocess.run(command, cwd=self.config.get('DEFAULT', 'config.project_path'), shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"PMD check failed: {result.stderr}")
            sys.exit(result.returncode)

    def get_report(self):
        report_path = self.config.get('DEFAULT', 'config.pmd_xml_file_path')
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
        namespaces = {'pmd': 'http://pmd.sourceforge.net/report/2.0.0'}
        pmd_root = ET.fromstring(report_content)

        for file_element in pmd_root.findall('.//pmd:file', namespaces):
            file_name = file_element.get('name')
            for violation in file_element.findall('.//pmd:violation', namespaces):
                issue = {
                    "id": str(uuid.uuid4().int)[:5],
                    "name": violation.get('rule'),
                    "explanation": violation.text.strip(),
                    "tags": violation.get('ruleset'),
                    "items": [
                        {
                            "patches": [],
                            "textrange": {
                                "file": file_name,
                                "startLine": int(violation.get('beginline')),
                                "endLine": int(violation.get('endline')),
                                "startColumn": int(violation.get('begincolumn')),
                                "endColumn": int(violation.get('endcolumn'))
                            }
                        }
                    ]
                }
                issues.append(issue)

        return issues
