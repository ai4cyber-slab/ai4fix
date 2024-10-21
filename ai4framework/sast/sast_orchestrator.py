import os
import subprocess
from utils.logger import logger
from management.repo_manager import RepoManager
from .tool_runner import ToolRunner
from .report_merger import ReportMerger
import sys


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
        self.projet_path = config.get('DEFAULT', 'config.project_path')

    def run_all(self, validation=False, java_file_path=None):
        """
        Run all configured SAST tools and merge their reports.

        This method orchestrates the entire SAST process, including:
        - Checking out the specified commit
        - Running PMD
        - Running Maven compile
        - Running SpotBugs
        - Running Trivy
        - Merging reports from all tools
        
        Args:
            validation (bool): If True, perform validation steps in all methods. Default is False.
        """
        try:
            if not validation and self.repo_manager.commit_hash:
                self.repo_manager.checkout_commit()
            self.tool_runner.run_pmd(validation=validation, java_file_path=java_file_path)
            if not validation:
                self.run_maven_compile()
            self.tool_runner.run_spotbugs(validation=validation)
            # self.tool_runner.run_trivy(validation=validation)
            self.report_merger.merge_reports(
                self.tool_runner.pmd_runner,
                self.tool_runner.spotbugs_runner,
                self.tool_runner.trivy_runner,
                validation=validation
            )
        finally:
            # self.repo_manager.revert_checkout()
            pass

    def run_maven_compile(self, validation=False):
        """
        Run Maven compile command for the project.

        This method attempts to compile the project using Maven,
        skipping tests to focus on compilation only.
        """
        try:
            logger.info("Maven compilation started...")

            # Use 'with' to safely manage the subprocess
            with subprocess.Popen(
                ['mvn', 'compile', '-Dmaven.compiler.incremental=true', '-DskipTests'],
                # ['mvn', 'compile', '-T 4C', '-Dmaven.compiler.incremental=true', '-DskipTests', '-B'],
                cwd=self.projet_path,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            ) as process:
                # Read and log stdout in real-time
                for line in process.stdout:
                    if not validation:
                        print(line.strip())  # Log each line of output as it's printed
                process.wait()  # Wait for the process to finish

            if process.returncode == 0:
                logger.info("Maven compile successful")
            else:
                logger.error(f"Maven compile failed with return code {process.returncode}")
                sys.exit(process.returncode)

        except Exception as e:
            logger.error(f"An error occurred during Maven compilation: {str(e)}")
            sys.exit(1)