import os
import subprocess
from utils.logger import logger
from management.repo_manager import RepoManager
from .tool_runner import ToolRunner
from .report_merger import ReportMerger


class SASTOrchestrator:
    """
    Orchestrates the execution of Static Application Security Testing (SAST) tools.

    This class manages the overall process of running various SAST tools,
    including checking out specific commits, running the tools, and merging reports.
    """

    def __init__(self, config):
        """
        Initialize the SASTOrchestrator with configuration settings.

        Args:
            config: Configuration object containing necessary settings.
        """
        self.repo_manager = RepoManager(
            config.get('DEFAULT', 'config.project_path'),
            config.get('CLASSIFIER', 'commit_sha')
        )
        self.tool_runner = ToolRunner(config, self.repo_manager)
        self.report_merger = ReportMerger(config)

    def run_all(self):
        """
        Run all configured SAST tools and merge their reports.

        This method orchestrates the entire SAST process, including:
        - Checking out the specified commit
        - Running PMD
        - Running Maven compile
        - Running SpotBugs
        - Running Trivy
        - Merging reports from all tools
        """
        try:
            self.repo_manager.checkout_commit()
            self.tool_runner.run_pmd()
            self.run_maven_compile()
            self.tool_runner.run_spotbugs()
            self.tool_runner.run_trivy()
            self.report_merger.merge_reports(
                self.tool_runner.pmd_runner,
                self.tool_runner.spotbugs_runner,
                self.tool_runner.trivy_runner
            )
        finally:
            self.repo_manager.revert_checkout()

    def run_maven_compile(self):
        """
        Run Maven compile command for the project.

        This method attempts to compile the project using Maven,
        skipping tests to focus on compilation only.
        """
        try:
            logger.info("Maven compilation started...")
            result = subprocess.run(
                ["mvn", "compile", "-DskipTests"],
                cwd=self.repo_manager.repo.working_dir,
                text=True
            )
            if result.returncode == 0:
                logger.info("Maven compile successful")
            else:
                logger.error("Maven compile failed")
        except Exception as e:
            logger.error(f"An error occurred during Maven compilation: {e}")


# Helper functions
def find_script_directory(script_name):
    """
    Find the directory containing a specified script.

    Args:
        script_name (str): The name of the script to find.

    Returns:
        str or None: The path to the directory containing the script,
                     or None if not found.
    """
    for root, dirs, files in os.walk(os.getcwd()):
        if script_name in files:
            return root
    return None