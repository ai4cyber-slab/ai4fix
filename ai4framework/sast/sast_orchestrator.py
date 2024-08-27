import os
import subprocess
from utils.logger import logger
from .repository_manager import RepositoryManager
from .tool_runner import ToolRunner
from .report_merger import ReportMerger

# project example use: struts github repo

class SASTOrchestrator:
    def __init__(self, config):
        self.repo_manager = RepositoryManager(
            config.get('DEFAULT', 'config.project_path'),
            config.get('CLASSIFIER', 'commit_sha')
        )
        self.tool_runner = ToolRunner(config, self.repo_manager)
        self.report_merger = ReportMerger(config)

    def run_all(self):
        try:
            self.repo_manager.checkout_commit()
            self.tool_runner.run_pmd()
            # self.run_maven_compile()
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
    for root, dirs, files in os.walk(os.getcwd()):
        if script_name in files:
            return root
    return None