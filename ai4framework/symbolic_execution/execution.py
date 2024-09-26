from symbolic_execution.analyzer import Analyzer
from symbolic_execution.json_processor import JSONProcessor
from utils.logger import logger
import os

class SymbolicExecution:
    """
    A class to manage symbolic execution analysis of a project.

    This class coordinates the process of running symbolic execution analysis
    on a project and processing the results.
    """

    def __init__(self, config):
        """
        Initialize the SymbolicExecution instance.

        Args:
            config (ConfigParser): Configuration object containing project settings.
        """
        self.config = config
        self.project_name = self.config.get("DEFAULT", "config.project_name")
        self.project_path = self.config.get("DEFAULT", "config.project_path")
        self.results_path = self.config.get("ANALYZER", "config.analyzer_results_path")
        self.analyzer_path = self.config.get("ANALYZER", "config.analyzer")
    
    def analyze(self):
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
        analyzer = Analyzer(self.analyzer_path, self.project_name, self.project_path, self.results_path)
        logger.info("Symbolic Execution Started ...")
        json_file = analyzer.run_analysis()
        cleaned_json_file = os.path.join(self.results_path, self.project_name, 'java', 'now', 'ai4vuln_issues.json')
        JSONProcessor.extract_and_clean_json(json_file, cleaned_json_file, self.project_path)

        logger.info("Analysis and JSON processing complete.")