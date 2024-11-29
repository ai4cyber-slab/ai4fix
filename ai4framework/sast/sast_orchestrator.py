import sys
import subprocess
import os

from utils.logger import logger
from .tool_runner import ToolRunner
from .report_merger import ReportMerger
from management.repo_manager import RepoManager


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
            config.get('DEFAULT', 'config.project_root'),
            config.get('DEFAULT', 'config.commit_sha')
        )
        self.tool_runner = ToolRunner(config, self.repo_manager)
        self.report_merger = ReportMerger(config)
        self.project_path = config.get('DEFAULT', 'config.project_root')

    def run_all(self, validation=False, tool=None, is_initial_round=True):
        """
        Run all configured SAST tools or specific ones based on the provided tool argument.

        This method orchestrates the SAST process, including:
        - Checking out the specified commit (if provided)
        - Running the specified tools (PMD, SpotBugs)
        - Merging reports from all tools
        
        Args:
            validation (bool): If True, perform validation steps in all methods. Default is False.
            tool (str): Specify the tool to run ("PMD" for PMD, "SB" for SpotBugs, or None for all). Default is None.
        """
        try:
            if not validation and self.repo_manager.commit_hash != '' and is_initial_round:
                self.repo_manager.checkout_commit()

            if tool is None or tool.upper() == "PMD":
                self.tool_runner.run_pmd()

            if not validation and (tool is None or tool.upper() == "SB"):
                self.run_maven_compile(validation=validation)

            if tool is None or tool.upper() == "SB":
                self.tool_runner.run_spotbugs()

            return self.report_merger.merge_reports(
                self.tool_runner.pmd_runner if tool is None or tool.upper() == "PMD" else None,
                self.tool_runner.spotbugs_runner if tool is None or tool.upper() == "SB" else None,
                validation=validation
            )
        except Exception as e:
            logger.error("An error occurred while running SAST tools: %s", e)
        finally:
            pass

    def run_maven_compile(self, validation=False):
        """
        Run Maven compile command for the project.

        This method attempts to compile the project using Maven,
        skipping tests to focus on compilation only.
        """
        try:
            logger.info("Maven compilation started...")

            with subprocess.Popen(
                ['mvn', 'compile', '-Dmaven.compiler.incremental=true', '-DskipTests', '-T', str(os.cpu_count())],
                cwd=self.project_path,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            ) as process:
                for line in process.stdout:
                    if not validation:
                        print(line.strip()) 
                process.wait()

            if process.returncode == 0:
                logger.info("Maven compile successful")
            else:
                logger.error(f"Maven compile failed with return code {process.returncode}")
                sys.exit(process.returncode)

        except Exception as e:
            logger.error(f"An error occurred during Maven compilation: {str(e)}")
            sys.exit(1)
            