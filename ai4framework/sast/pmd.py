import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import tempfile
from utils.logger import logger
from pathlib import Path


class PMDRunner:
    """
    A class to run PMD (Programming Mistake Detector) static code analysis tool and parse its results.
    """

    def __init__(self, config):
        """
        Initialize the PMDRunner with configuration settings.

        Args:
            config: Configuration object containing necessary settings for PMD execution.
        """
        self.config = config
        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.report_path = os.path.join(self.project_path, '.ai4framework','out', 'pmd.xml')
        self.cache_dir = os.path.join(os.sep, 'tmp', 'pmd-cache')
        os.makedirs(os.path.dirname(self.report_path), exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

    def run(self, files_to_analyze):
        """
        Run PMD on the specified Java files.

        Args:
            files_to_analyze (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the PMD check fails.
        """
        if not files_to_analyze:
            logger.warning("No files to analyze.")
            sys.exit(1)

        pmd_bin = os.environ.get('PMD_BIN')
        ruleset_path = self.config.get(
            'SAST', 'config.pmd_ruleset',
            fallback=os.path.join(os.sep, 'app', 'utils', 'PMD-config.xml')
        )

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write('\n'.join(files_to_analyze))
            temp_file_path = temp_file.name

        try:
            command = [
                pmd_bin, "check",
                "--file-list", temp_file_path,
                "-R", ruleset_path,
                "-f", "xml",
                "-r", self.report_path,
                "--no-fail-on-violation",
                "--no-fail-on-error",
                "--cache", self.cache_dir,
                "--threads", str(os.cpu_count())
            ]

            result = subprocess.run(
                command, cwd=self.project_path, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            if result.returncode == 0:
                logger.info("PMD check completed successfully.")
            else:
                logger.error(f"PMD check failed with return code {result.returncode}: {result.stderr}")
                sys.exit(result.returncode)

        except Exception as e:
            logger.error(f"An error occurred while running PMD: {str(e)}")
            sys.exit(1)
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file: {str(e)}")

    def get_report(self):
        """
        Retrieve the PMD report content.

        Returns:
            str or None: The content of the PMD report if it exists, None otherwise.
        """
        try:
            with open(self.report_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            logger.debug("PMD report not found.")
            return None

    def parse_report(self):
        """
        Parse the PMD report XML and extract issues.

        Returns:
            list: A list of dictionaries, each representing an issue found by PMD.
        """
        report_content = self.get_report()
        if not report_content:
            logger.debug("No report to parse.")
            return []

        namespaces = {'pmd': 'http://pmd.sourceforge.net/report/2.0.0'}
        issues = []
        try:
            pmd_root = ET.fromstring(report_content)
            for file_element in pmd_root.findall('.//pmd:file', namespaces):
                file_name = file_element.get('name', '').replace(f"{self.project_path}/", '', 1)
                for violation in file_element.findall('.//pmd:violation', namespaces):
                    start_line = violation.get('beginline')
                    end_line = violation.get('endline')
                    start_column = violation.get('begincolumn')
                    end_column = violation.get('endcolumn')

                    if not all([start_line, end_line, start_column, end_column]):
                        continue

                    issue = {
                        "id": f"PMD-{str(len(issues) + 1).zfill(4)}",
                        "name": violation.get('rule', 'Unknown Rule'),
                        "explanation": (violation.text or "No explanation provided.").strip(),
                        "tags": "PMD",
                        "items": [
                            {
                                "patches": [],
                                "textrange": {
                                    "file": file_name,
                                    "startLine": int(start_line),
                                    "endLine": int(end_line),
                                    "startColumn": int(start_column),
                                    "endColumn": int(end_column)
                                }
                            }
                        ]
                    }
                    if 'src' in Path(file_name).parts:
                        issues.append(issue)

        except ET.ParseError as e:
            logger.error(f"Failed to parse PMD report: {e}")

        return issues