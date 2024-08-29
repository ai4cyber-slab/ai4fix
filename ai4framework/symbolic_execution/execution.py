from symbolic_execution.analyzer import Analyzer
from symbolic_execution.json_processor import JSONProcessor
from utils.logger import logger

class SymbolicExecution:
    def __init__(self, config):
        self.config = config
        self.project_name = self.config.get("DEFAULT", "config.project_name")
        self.project_path = self.config.get("DEFAULT", "config.project_path")
        self.results_path = self.config.get("ANALYZER", "config.analyzer_results_path")
        self.analyzer_path = self.config.get("ANALYZER", "config.analyzer")
    
    def analyze(self):
        analyzer = Analyzer(self.analyzer_path, self.project_name, self.project_path, self.results_path)
        json_file = analyzer.run_analysis()

        cleaned_json_file = f'{self.results_path}/{self.project_name}/java/now/extracted_issues.json'
        JSONProcessor.extract_and_clean_json(json_file, cleaned_json_file)

        logger.info("Analysis and JSON processing complete.")