from core.security_classifier import SecurityClassifier
from core.sast_engine import SASTEngine
from core.symbolic_execution import SymbolicExecution
from config.common_config import ConfigManager
from utils.logger import logger
import argparse
import os
import sys

class WorkflowFramework:
    def __init__(self):
        self.config = ConfigManager.get_config()
        self.security_classifier = SecurityClassifier(self.config)
        # self.security_annotator = SecurityAnnotator(self.config)
        # self.symbolic_executor = SymbolicExecutor(self.config)
        # self.fix_generator = FixGenerator(self.config)

        # self.sast_engine = SASTEngine(self.config)
        self.symbolic_execution = SymbolicExecution(self.config)

        # self.test_generator = TestGenerator(self.config)
        # self.verifier = Verifier(self.config)
        # self.sorter = Sorter(self.config)

    def execute_workflow(self, project_path):
        logger.info("Starting workflow execution")
        # classified_code = self.security_classifier.classify(project_path)
        # annotated_code = self.security_annotator.annotate(classified_code)
        # issues_file = self.symbolic_executor.execute(annotated_code)

        # self.sast_engine.analyze(source_code_path)
        self.symbolic_execution.analyze('user_auth')

        # logger.info("Workflow execution completed")
        pass


if __name__ == "__main__":
    framework = WorkflowFramework()
    config = ConfigManager.get_config()
    project_path = config.get('DEFAULT', 'config.project_path')
    framework.execute_workflow(project_path)

    # if len(sys.argv) != 2:
    #     print("Usage: python main.py /path/to/config.properties")
    #     sys.exit(1)

    # config_file_path = sys.argv[1]

    # framework = WorkflowFramework(config_file_path)
    # config = framework.config
    # project_path = config.get('DEFAULT', 'config.project_path')
    
    # framework.execute_workflow(project_path)

