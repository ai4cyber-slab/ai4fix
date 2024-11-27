import os
import sys
import uuid
import subprocess
import xml.etree.ElementTree as ET
from utils.logger import logger


class SpotBugsRunner:
    """
    A class to run SpotBugs static code analysis tool and parse its results.
    """

    def __init__(self, config):
        """
        Initialize the SpotBugsRunner with configuration settings.

        Args:
            config: Configuration object containing necessary settings for SpotBugs execution.
        """
        self.config = config
        self.report_path = os.path.join(os.sep, 'app','sast','out','spotbugs.xml')
        self.project_path = self.config.get('DEFAULT', 'config.project_root')

    def find_classes_directories(self, root_path):
        """
        Find all 'target/classes' directories in a Maven multi-module project.
        """
        return [
            os.path.join(dirpath, "classes")
            for dirpath, dirnames, filenames in os.walk(root_path)
            if dirpath.endswith("target") and "classes" in dirnames
        ]

    def run(self, files_to_analyze):
        """
        Run SpotBugs on the specified Java files.

        Args:
            files_to_analyze (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the SpotBugs check fails.
        """
        if not files_to_analyze:
            logger.warning("There are no files to be analyzed.")
            sys.exit(1)

        spotbugs_bin = self.config.get(
            'SAST', 'config.spotbugs_bin',
            fallback=os.path.join(os.sep, 'opt', 'spotbugs-4.8.6', 'bin', 'spotbugs')
        )

        to_analyze = (
            ' '.join(self.find_classes_directories(self.project_path))
            if len(files_to_analyze) > 500 else
            ' '.join(files_to_analyze)
        )

        command = f"{spotbugs_bin} -textui -xml:withMessages={self.report_path} {to_analyze}"

        try:
            process = subprocess.run(
                command, cwd=self.project_path,
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if process.returncode == 0:
                logger.info("SpotBugs check completed successfully.")
            else:
                logger.error(f"SpotBugs check failed with return code {process.returncode}: {process.stderr}")
                sys.exit(process.returncode)
        except Exception as e:
            logger.error(f"An error occurred while running SpotBugs: {str(e)}")
            sys.exit(1)

    def get_report(self, validation=False):
        """
        Retrieve the SpotBugs report content.

        Returns:
            str or None: The content of the SpotBugs report if it exists, None otherwise.
        """
        if os.path.exists(self.report_path):
            with open(self.report_path, 'r') as file:
                return file.read()
        return None

    def parse_report(self, limit=100, validation=False):
        """
        Parse the SpotBugs report XML and extract issues.

        Returns:
            list: A list of dictionaries, each representing an issue found by SpotBugs.
        """
        report_content = self.get_report(validation=validation)
        if not report_content:
            logger.warning("No report found to parse.")
            return []

        issues = []
        spotbugs_root = ET.fromstring(report_content)

        for bug_instance in spotbugs_root.findall('.//BugInstance'):
            issue = {
                "id": str(uuid.uuid4().int)[:5],
                "name": bug_instance.get('type', '').strip(),
                "explanation": (bug_instance.find('LongMessage').text or "No detailed explanation available.").strip(),
                "tags": "SB",
                "items": []
            }

            first_source_line = bug_instance.find('SourceLine')
            class_data = bug_instance.find('Class')
            class_start = class_data.find('SourceLine').get('start') if class_data is not None else '1'
            class_end = class_data.find('SourceLine').get('end') if class_data is not None else '1'

            if first_source_line is not None:
                relative_path = first_source_line.get('sourcepath', 'unknown file')
                full_path = find_base_dir_path(self.project_path, relative_path) or 'unknown file'

                start_line = first_source_line.get('start', class_start)
                end_line = first_source_line.get('end', class_end)
                start_column = first_source_line.get('startBytecode', '1')
                end_column = first_source_line.get('endBytecode', first_source_line.get('startBytecode', '1'))

                if not all([start_line, end_line, start_column, end_column]):
                    continue

                textrange = {
                    "file": full_path,
                    "startLine": int(start_line),
                    "endLine": int(end_line),
                    "startColumn": int(start_column),
                    "endColumn": int(end_column)
                }
                issue["items"].append({"patches": [], "textrange": textrange})

            issues.append(issue)

        return issues


def find_base_dir_path(project_root, target_path, test_dir=False):
    """
    Find the base directory path for a given target efficiently.

    Args:
        project_root (str): Root directory of the project.
        target_path (str): The target path to locate.
        test_dir (bool): Whether to look in the 'test' directory. Defaults to 'main'.

    Returns:
        str or None: The relative path of the found file from the project root, or None if not found.
    """
    target_path = os.path.join('src', 'test' if test_dir else 'main', 'java', target_path)
    norm_target_path = os.path.normpath(target_path)
    for dirpath, _, filenames in os.walk(project_root):
        for file in filenames:
            if file == os.path.basename(norm_target_path):
                current_file_path = os.path.relpath(os.path.join(dirpath, file), project_root)
                if current_file_path.endswith(norm_target_path):
                    return current_file_path
    return None