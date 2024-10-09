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
        self.report_path = self.config.get('REPORT', 'config.spotbugs_report_path', fallback=os.path.join(os.sep, 'app','sast','out','spotbugs.xml'))
        self.BASE_SRC_DIR = os.path.join('src', 'main', 'java')
        self.BASE_TEST_DIR = os.path.join('src', 'test', 'java')

    # def run(self, changed_files):
    #     """
    #     Run SpotBugs on the specified Java files.

    #     Args:
    #         changed_files (list): List of Java file paths to analyze.

    #     Raises:
    #         SystemExit: If the SpotBugs check fails.
    #     """
    #     command = (
    #         f"{self.config.get('DEFAULT', 'config.spotbugs_bin')} -textui "
    #         f"-xml:withMessages={self.report_path} "
    #         f"{' '.join(changed_files)}"
    #     )
    #     result = subprocess.run(command, cwd=self.config.get('DEFAULT', 'config.project_path'), shell=True, capture_output=True, text=True)

    #     if result.returncode != 0:
    #         logger.error(f"SpotBugs check failed: {result.stderr}")
    #         sys.exit(result.returncode)
    def run(self, changed_files):
        """
        Run SpotBugs on the specified Java files.

        Args:
            changed_files (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the SpotBugs check fails.
        """
        spotbugs_bin = self.config.get('DEFAULT', 'config.spotbugs_bin', fallback=os.path.join(os.sep, 'opt','spotbugs-4.8.6','bin','spotbugs'))
        command = (
            f"{spotbugs_bin} -textui "
            f"-xml:withMessages={self.report_path} "
            f"{' '.join(changed_files)}"
        )

        try:
            # Use 'with' to safely manage the subprocess
            with subprocess.Popen(
                command, cwd=self.config.get('DEFAULT', 'config.project_path'),
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ) as process:
                stdout, stderr = process.communicate()

            if process.returncode == 0:
                logger.info("SpotBugs check completed successfully.")
            else:
                logger.error(f"SpotBugs check failed with return code {process.returncode}: {stderr}")
                sys.exit(process.returncode)

        except Exception as e:
            logger.error(f"An error occurred while running SpotBugs: {str(e)}")
            sys.exit(1)


    def get_report(self):
        """
        Retrieve the SpotBugs report content.

        Returns:
            str or None: The content of the SpotBugs report if it exists, None otherwise.
        """
        if os.path.exists(self.report_path):
            with open(self.report_path, 'r') as file:
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
                relative_path = first_source_line.get('sourcepath', 'unknown file')
                
                if relative_path != 'unknown file':
                    normalized_relative_path = os.path.normpath(relative_path)
                    if os.path.exists(os.path.join(self.config.get("DEFAULT", "config.project_path"), self.BASE_SRC_DIR, normalized_relative_path)):
                        full_path = os.path.join(self.BASE_SRC_DIR, normalized_relative_path)
                    elif os.path.exists(os.path.join(self.config.get("DEFAULT", "config.project_path"), self.BASE_TEST_DIR, normalized_relative_path)):
                        full_path = os.path.join(self.BASE_TEST_DIR, normalized_relative_path)
                else:
                    full_path = 'unknown file'
                textrange = {
                    "file": full_path,
                    "startLine": int(first_source_line.get('start', '1')),
                    "endLine": int(first_source_line.get('end', first_source_line.get('start', '1'))),
                    "startColumn": int(first_source_line.get('startBytecode', '0')),
                    "endColumn": int(first_source_line.get('endBytecode', first_source_line.get('startBytecode', '0')))
                }
                issue["items"].append({"patches": [], "textrange": textrange})
            
            issues.append(issue)

        return issues
