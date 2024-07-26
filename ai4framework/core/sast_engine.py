import subprocess
import json
from utils.logger import logger

class SASTEngine:
    def __init__(self, config):
        self.config = config

    def analyze(self, source_code_path):
        logger.debug("Analyzing source code with SAST tool: SpotBugs")
    
        
        # Convert XML report to JSON
        json_report = self.convert_xml_to_json("spotbugs_xml_file_path", "spotbugs_output_file")
        return json_report

    def convert_xml_to_json(self, xml_file_path, json_file_path):
        logger.debug("Converting XML report to JSON")
        pass