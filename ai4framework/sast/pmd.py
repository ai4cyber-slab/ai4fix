import os
import sys
import uuid
import subprocess
import xml.etree.ElementTree as ET

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
        self.report_path = os.path.join(os.sep, 'app','sast','out','pmd.xml')
        self.project_path = self.config.get('DEFAULT', 'config.project_root')


    def run(self, files_to_analyze):
        """
        Run PMD on the specified Java files.

        Args:
            files_to_analyze (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the PMD check fails.
        """
        if files_to_analyze == []:
            print('There are no files to be analyzed.')
            sys.exit(1)

        report_dir = os.path.dirname(self.report_path)
        
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        cache_dir = os.path.join(os.sep, 'tmp', 'pmd-cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        command = (
            f"{self.config.get('SAST', 'config.pmd_bin', fallback=os.path.join(os.sep, 'opt', 'pmd-bin-7.4.0', 'bin', 'pmd'))} check "
            f"-d {','.join(files_to_analyze)} "
            f"-R {self.config.get('SAST', 'config.pmd_ruleset', fallback=os.path.join(os.sep, 'app', 'utils', 'PMD-config.xml'))} "
            f"-f xml "
            f"-r {self.report_path} "
            "--no-fail-on-violation "
            "--verbose "
            f"--cache {cache_dir}"  # Cache to support Incremental Analysis
        )

        try:
            with subprocess.Popen(command, cwd=self.project_path, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                stdout, stderr = process.communicate()

            if process.returncode == 0:
                logger.info("PMD check completed successfully.")
            else:
                logger.error(f"PMD check failed with return code {process.returncode}: {stderr}")
                sys.exit(process.returncode)

        except Exception as e:
            logger.error(f"An error occurred while running PMD: {str(e)}")
            sys.exit(1)


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
            file_name = file_element.get('name').replace(self.project_path + '/', '')
            for violation in file_element.findall('.//pmd:violation', namespaces):
                issue = {
                    "id": str(uuid.uuid4().int)[:5],
                    "name": violation.get('rule'),
                    "explanation": violation.text.strip(),
                    "tags": "PMD",
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
