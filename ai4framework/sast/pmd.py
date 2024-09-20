import subprocess
import os
import sys
import xml.etree.ElementTree as ET
import uuid
from utils.logger import logger

class PMDRunner:
    """
    A class to run PMD (Programming Mistake Detector) static code analysis tool and parse its results.

    This class provides methods to execute PMD on Java files, retrieve the generated report,
    and parse the report into a structured format.
    """

    def __init__(self, config):
        """
        Initialize the PMDRunner with configuration settings.

        Args:
            config: Configuration object containing necessary settings for PMD execution.
        """
        self.config = config
        self.report_path = self.config.get('REPORT', 'config.pmd_report_path', fallback='/app/sast/out/pmd.xml')

    def run(self, java_files):
        """
        Run PMD on the specified Java files.

        Args:
            java_files (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the PMD check fails.
        """
        report_dir = os.path.dirname(self.report_path)
    
        # Ensure the directory for the report exists
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        command = (
            f"{self.config.get('DEFAULT', 'config.pmd_bin')} check "  # Path to PMD binary
            f"-d {','.join(java_files)} "  # Java files with the /user_project path prepended
            f"-R {self.config.get('DEFAULT', 'config.pmd_ruleset', fallback='/app/utils/PMD-config.xml')} "  # Path to PMD ruleset
            f"-f xml "  # Output format
            f"-r {self.report_path} "  # Output report path
            "--no-fail-on-violation"
        )

        result = subprocess.run(command, cwd=self.config.get('DEFAULT', 'config.project_path'), shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"PMD check failed: {result.stderr}")
            sys.exit(result.returncode)

    def get_report(self):
        """
        Retrieve the PMD report content.

        Returns:
            str or None: The content of the PMD report if it exists, None otherwise.
        """
        if os.path.exists(self.report_path):
            with open(self.report_path, 'r') as file:
                return file.read()
        return None

    def parse_report(self):
        """
        Parse the PMD report XML and extract issues.

        Returns:
            list: A list of dictionaries, each representing an issue found by PMD.
        """
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
