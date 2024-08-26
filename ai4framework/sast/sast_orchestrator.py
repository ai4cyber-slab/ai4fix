import os
import subprocess
import git
import json
from .pmd import PMDRunner
from .spotbugs import SpotBugsRunner
from .trivy import TrivyRunner
from utils.logger import logger

class SASTOrchestrator:
    def __init__(self, config):
        self.config = config
        self.repo_path = self.config.get('DEFAULT', 'config.project_path')
        self.commit_hash = self.config.get('CLASSIFIER', 'commit_sha')
        self.repo = git.Repo(self.repo_path)


        self.pmd_runner = PMDRunner(self.config)
        self.spotbugs_runner = SpotBugsRunner(self.config)
        self.trivy_runner = TrivyRunner(self.config)

    def checkout_commit(self):
        logger.info(f"Checking out commit {self.commit_hash}...")
        try:
            self.repo.git.checkout('-f', self.commit_hash)
            logger.info(f"Checked out to commit {self.commit_hash}.")
        except Exception as e:
            logger.error(f"Failed to checkout commit {self.commit_hash}: {e}")
            raise

    def get_changed_files(self):
        try:
            result = subprocess.run(
                ['git', 'show', '--name-only', '--pretty=format:', self.commit_hash],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.repo_path,
                text=True,
                check=True
            )
            changed_files = result.stdout.strip().split('\n')
            return changed_files
        except subprocess.CalledProcessError as e:
            logger.error(f"An error occurred: {e.stderr}")
            return []

    def revert_checkout(self):
        logger.info("Reverting to the previous branch/state...")
        try:
            self.repo.git.checkout('-')
            logger.info("Reverted to the previous branch/state.")
        except Exception as e:
            logger.error(f"Failed to revert checkout: {e}")
            raise

    def run_maven_compile(self):
        try:
            logger.info("maven compilation started...")
            result = subprocess.run(["mvn", "compile", "-DskipTests"], cwd=self.repo_path, text=True)
            
            if result.returncode == 0:
                logger.debug("Maven compile successful")
            else:
                logger.error("Maven compile failed")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

    def run_pmd(self):
        script_name = "pmd.py"
        script_dir = find_script_directory(script_name)
        logger.info(f"Running PMD... (script: {script_name}, directory: {script_dir})")
        changed_java_files = self.get_changed_files()
        self.pmd_runner.run(changed_java_files)

    def run_spotbugs(self):
        script_name = "spotbugs.py"
        script_dir = find_script_directory(script_name)
        logger.info(f"Running Spotbugs... (script: {script_name}, directory: {script_dir})")
        class_changed_files = self.find_class_changed_files()
        self.spotbugs_runner.run(class_changed_files)

    def run_trivy(self):
        script_name = "trivy.py"
        script_dir = find_script_directory(script_name)
        logger.info(f"Running Trivy... (script: {script_name}, directory: {script_dir})")
        self.trivy_runner.run()

    def merge_reports(self):
        logger.info("Merging reports...")
        try:
            # Run and extract issues from PMD
            pmd_report_path = self.config.get("REPORT", "config.pmd_report_path", fallback=None)
            spotbugs_report_path = self.config.get("REPORT", "config.spotbugs_report_path", fallback=None)
            trivy_report_path = self.config.get("REPORT", "config.trivy_report_path", fallback=None)
            output_path = self.config.get("ISSUES", "config.sast_issues_path", fallback=None)

            issues = []

            if pmd_report_path:
                issues.extend(self.pmd_runner.parse_report())

            if spotbugs_report_path:
                issues.extend(self.spotbugs_runner.parse_report())

            if trivy_report_path:
                issues.extend(self.trivy_runner.parse_report())

            # Ensure the directory exists
            directory = os.path.dirname(output_path)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            # Write the issues to the JSON file
            with open(output_path, 'w') as json_file:
                json.dump(issues, json_file, indent=4)

            logger.info("Reports merged successfully.")
        except Exception as e:
            logger.error(f"Failed to merge reports: {e}")

    def find_class_changed_files(self):
        project_root = self.repo_path
        class_files = []

        for java_file in self.get_changed_files():
            if not java_file.endswith('.java'):
                logger.warn(f"Skipping non-Java file: {java_file}")
                continue

            class_file_path = find_class_file_from_java(java_file, project_root)
            if class_file_path:
                class_files.append(class_file_path)

        return class_files if class_files else []

    def run_all(self):
        try:
            self.checkout_commit()
            self.run_pmd()
            # self.run_maven_compile()
            self.run_spotbugs()
            self.run_trivy()
            self.merge_reports()
        finally:
            self.revert_checkout()




# Helper functions
def find_script_directory(script_name):
    for root, dirs, files in os.walk(os.getcwd()):
        if script_name in files:
            return root
    return None

def find_class_file_from_java(java_file_path, project_root):
    path_parts = java_file_path.strip(os.path.sep).split(os.path.sep)
    submodule_directory = path_parts[0] if not path_parts[0].startswith("src") else ""

    if 'src/main/java' in java_file_path:
        relative_class_path = java_file_path.split('src/main/java/', 1)[1]
        output_dir = 'target/classes'
    elif 'src/test/java' in java_file_path:
        relative_class_path = java_file_path.split('src/test/java/', 1)[1]
        output_dir = 'target/test-classes'
    else:
        logger.debug(f"Invalid path: {java_file_path}")
        return None

    relative_class_path = os.path.splitext(relative_class_path)[0] + '.class'
    class_file_path = os.path.join(project_root, submodule_directory, output_dir, relative_class_path)
    logger.debug(f"Looking for .class file at: {class_file_path}")

    if os.path.isfile(class_file_path):
        logger.debug(f"Class file found for: {java_file_path}")
        return class_file_path
    else:
        logger.debug(f"Class file not found for: {java_file_path}")
        return None
