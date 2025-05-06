import os
import re
import subprocess
from pathlib import Path

from utils.logger import logger
from symbolic_execution.analyzer import Analyzer
from symbolic_execution.json_processor import JSONProcessor


class SymbolicExecution:
    """
    A class to manage symbolic execution analysis of a project.

    This class coordinates the process of running symbolic execution analysis
    on a project and processing the results.
    """

    def __init__(self, config, single_file=None):
        """
        Initialize the SymbolicExecution instance.

        Args:
            config (ConfigParser): Configuration object containing project settings.
        """
        self.config = config
        self.project_name = self.config.get('DEFAULT', 'config.project_name')
        self.project_path = self.config.get('DEFAULT', 'config.project_root')
        self.results_path = self.config.get("DEFAULT", "config.analyzer_results_path")
        self.analyzer_path = os.environ.get('ANALYZER_BIN')
        self.filter_list = self.config.get('DEFAULT', 'config.filter')
        self.single_file = single_file
    def analyze(self, validation=False):
        """
        Perform symbolic execution analysis on the project.

        This method orchestrates the entire process of symbolic execution:
        1. Initializes and runs the analyzer
        2. Processes and cleans the resulting JSON file

        The actual analysis is performed by the Analyzer class, and this method
        serves as a high-level controller for the process.

        Note: This method doesn't return a value, as its purpose is to execute
        the analysis process and log the results.
        """
        if self.single_file:
            match = re.search(r"(/tmp/patch_[^/]+?)/", self.single_file)
            if match:
                temp_dir = match.group(1)
                self.results_path = self.results_path.replace(os.environ.get("PROJECT_PATH"), temp_dir)
                self.project_path = temp_dir
                self.project_name = "SE_PROJ"
        analyzer = Analyzer(self.analyzer_path, self.project_name, self.project_path, self.results_path, self.filter_list, self.single_file)
        try:
            logger.info("Symbolic Execution Started ...")
            json_file = analyzer.run_analysis()
            cleaned_json_file = os.path.join(self.results_path, self.project_name, 'java', 'now', 'ai4vuln_issues.json') if not validation else os.path.join(self.results_path, self.project_name, 'java', 'now', 'ai4vuln_issues_temp.json')
            return JSONProcessor.extract_and_clean_json(json_file, cleaned_json_file, self.project_path)
        except Exception as e:
            logger.error(f"AI4VULN ERROR: {e}")
            return []