import subprocess
import os
import sys
import xml.etree.ElementTree as ET
import uuid
from utils.logger import logger

class SpotBugsRunner:
    """
    A class to run SpotBugs static code analysis tool and parse its results.

    This class provides methods to execute SpotBugs on Java files, retrieve the generated report,
    and parse the report into a structured format.
    """

    def __init__(self, config):
        """
        Initialize the SpotBugsRunner with configuration settings.

        Args:
            config: Configuration object containing necessary settings for SpotBugs execution.
        """
        self.config = config

    def run(self, changed_files):
        """
        Run SpotBugs on the specified Java files.

        Args:
            changed_files (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the SpotBugs check fails.
        """
        command = (
            f"{self.config.get('DEFAULT', 'config.spotbugs_bin')} -textui "
            f"-xml:withMessages={self.config.get('REPORT', 'config.spotbugs_report_path')} "
            f"{' '.join(changed_files)}"
        )
        result = subprocess.run(command, cwd=self.config.get('DEFAULT', 'config.project_path'), shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"SpotBugs check failed: {result.stderr}")
            sys.exit(result.returncode)

    def get_report(self):
        """
        Retrieve the SpotBugs report content.

        Returns:
            str or None: The content of the SpotBugs report if it exists, None otherwise.
        """
        report_path = self.config.get('REPORT', 'config.spotbugs_report_path')
        if os.path.exists(report_path):
            with open(report_path, 'r') as file:
                return file.read()
        return None

    def parse_report(self):
        """
        Parse the SpotBugs report XML and extract issues.

        Returns:
            list: A list of dictionaries, each representing an issue found by SpotBugs.
        """
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
