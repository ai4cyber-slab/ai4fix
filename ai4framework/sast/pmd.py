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
        os.makedirs(os.path.dirname(self.report_path), exist_ok=True)

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
        excluded_categories = {'Code Style', 'Design', 'Documentation'}
        try:
            pmd_root = ET.fromstring(report_content)
            for file_element in pmd_root.findall('.//pmd:file', namespaces):
                file_name = file_element.get('name', '').replace(f"{self.project_path}/", '', 1)
                for violation in file_element.findall('.//pmd:violation', namespaces):
                    ruleset = violation.get('ruleset')
                    if ruleset in excluded_categories:
                        continue

                    start_line = violation.get('beginline')
                    end_line = violation.get('endline')
                    start_column = violation.get('begincolumn')
                    end_column = violation.get('endcolumn')
                    priority = violation.get('priority')

                    if not all([start_line, end_line, start_column, end_column, priority]):
                        continue

                    severity = map_rank_to_severity(priority)
                    complexity = int(end_line) - int(start_line) + 1

                    issue = {
                        "id": f"PMD-{str(len(issues) + 1).zfill(4)}",
                        "name": violation.get('rule', 'Unknown Rule'),
                        "severity": severity,
                        "complexity": complexity,
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

        rule_frequency = {}
        for issue in issues:
            rule_name = issue["name"]
            rule_frequency[rule_name] = rule_frequency.get(rule_name, 0) + 1

        severity_mapping = {
            "High": 5,
            "Medium-High": 4,
            "Medium": 3,
            "Medium-Low": 2,
            "Low": 1,
            "Unknown": 0
        }

        def calculate_score(severity_numeric, complexity, frequency):
            severity_weight = 3
            complexity_weight = 1
            frequency_weight = 2
            return severity_numeric * severity_weight + complexity * complexity_weight + frequency * frequency_weight

        for issue in issues:
            sev_numeric = severity_mapping.get(issue["severity"], 0)
            freq = rule_frequency.get(issue["name"], 1)
            issue["score"] = calculate_score(sev_numeric, issue["complexity"], freq)

        return issues
    
def map_rank_to_severity(priority):
    priority = int(priority)
    if priority == 1:
        return "High"
    elif priority == 2:
        return "Medium-High"
    elif priority == 3:
        return "Medium"
    elif priority == 4:
        return "Medium-Low"
    elif priority == 5:
        return "Low"
    else:
        return "Unknown"