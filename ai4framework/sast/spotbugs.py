import os
import sys
import uuid
import subprocess
import xml.etree.ElementTree as ET

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
        self.report_path = os.path.join(os.sep, 'app','sast','out','spotbugs.xml')
        self.project_path = self.config.get('DEFAULT', 'config.project_root')

    def run(self, files_to_analyze):
        """
        Run SpotBugs on the specified Java files.

        Args:
            files_to_analyze (list): List of Java file paths to analyze.

        Raises:
            SystemExit: If the SpotBugs check fails.
        """
        if files_to_analyze == []:
            logger.warning('There are no files to be analyzed.')
            sys.exit(1)

        spotbugs_bin = self.config.get('SAST', 'config.spotbugs_bin', fallback=os.path.join(os.sep, 'opt','spotbugs-4.8.6','bin','spotbugs'))
        command = (
            f"{spotbugs_bin} -textui "
            f"-xml:withMessages={self.report_path} "
            f"{' '.join(files_to_analyze)}"
        )

        try:
            with subprocess.Popen(
                command, cwd=self.project_path,
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


    def get_report(self, validation=False):
        """
        Retrieve the SpotBugs report content.

        Returns:
            str or None: The content of the SpotBugs report if it exists, None otherwise.
        """
        report = self.report_path
        if os.path.exists(report):
            with open(report, 'r') as file:
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
                "name": bug_instance.get('type').strip() if bug_instance.get('type') is not None else "Unknown Issue",
                "explanation": bug_instance.find('LongMessage').text.strip() if bug_instance.find('LongMessage') is not None else "No detailed explanation available.",
                "tags": "SB",
                "items": []
            }
                
            first_source_line = bug_instance.find('SourceLine')
            class_end_value = bug_instance.find('Class').find('SourceLine').get('end') if bug_instance.find('Class') is not None else None
            class_start_value = bug_instance.find('Class').find('SourceLine').get('start') if bug_instance.find('Class') is not None else None
            if first_source_line is not None:
                relative_path = first_source_line.get('sourcepath', 'unknown file')
                src_base_dir = find_base_dir_path(self.project_path, relative_path)
                test_base_dir = find_base_dir_path(self.project_path, relative_path, test_dir=True)
                    
                if relative_path != 'unknown file':
                    if src_base_dir:
                        full_path = src_base_dir
                    elif test_base_dir:
                        full_path = test_base_dir
                    else:
                        full_path = 'unknown file'
                else:
                    full_path = 'unknown file'
                    
                textrange = {
                    "file": full_path,
                    "startLine": int(first_source_line.get('start', class_start_value)),
                    "endLine": int(first_source_line.get('end', class_end_value)),
                    "startColumn": int(first_source_line.get('startBytecode', '0')),
                    "endColumn": int(first_source_line.get('endBytecode', first_source_line.get('startBytecode', '0')))
                }
                issue["items"].append({"patches": [], "textrange": textrange})
                
            issues.append(issue)

            return issues


def find_base_dir_path(project_root, target_path, test_dir=False):
    if not test_dir:
        target_path = os.path.join('src', 'main', 'java', target_path)
    else:
        target_path = os.path.join('src', 'test', 'java', target_path)

    norm_target_path = os.path.normpath(target_path)

    # Walk through the project directory
    for dirpath, dirnames, filenames in os.walk(project_root):
        # Reconstruct relative path to each file from project root
        for file in filenames:
            # Absolute path of the current file
            current_file_path = os.path.join(dirpath, file)
            
            # Check if the file matches the end of the target path
            if current_file_path.endswith(norm_target_path):
                return current_file_path.replace(project_root + '/', '')  # Return the path where it was found

    # If not found
    return None
