import subprocess
import os
import sys
import xml.etree.ElementTree as ET
import uuid
from utils.logger import logger

class SpotBugsRunner:
    def __init__(self, config):
        self.config = config

    def run(self, changed_files):
        command = (
            f"{self.config.get('DEFAULT', 'config.spotbugs_bin')} -textui "
            f"-xml:withMessages={self.config.get('DEFAULT', 'config.spotbugs_xml_file_path')} "
            f"{' '.join(changed_files)}"
        )
        result = subprocess.run(command, cwd=self.config.get('DEFAULT', 'config.project_path'), shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"SpotBugs check failed: {result.stderr}")
            sys.exit(result.returncode)

    def get_report(self):
        report_path = self.config.get('DEFAULT', 'config.spotbugs_xml_file_path')
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
        spotbugs_root = ET.fromstring(report_content)

        for bug_instance in spotbugs_root.findall('.//BugInstance'):
            issue = {
                "id": str(uuid.uuid4().int)[:5],
                "name": bug_instance.get('type').strip() if bug_instance.get('type') is not None else "Unknown Issue",
                "explanation": bug_instance.find('LongMessage').text.strip() if bug_instance.find('LongMessage') is not None else "No detailed explanation available.",
                "tags": ("CWE-" + bug_instance.get('cweid')) if bug_instance.get('cweid') is not None else "CWE-XXXX",
                "items": []
            }
            
            first_source_line = bug_instance.find('SourceLine')
            if first_source_line is not None:
                textrange = {
                    "file": first_source_line.get('sourcepath', 'unknown file'),
                    "startLine": int(first_source_line.get('start', '1')),
                    "endLine": int(first_source_line.get('end', first_source_line.get('start', '1'))),
                    "startColumn": int(first_source_line.get('startBytecode', '0')),
                    "endColumn": int(first_source_line.get('endBytecode', first_source_line.get('startBytecode', '0')))
                }
                issue["items"].append({"patches": [], "textrange": textrange})
            
            issues.append(issue)

        return issues
