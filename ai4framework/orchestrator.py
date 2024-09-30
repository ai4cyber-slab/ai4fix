from symbolic_execution.execution import SymbolicExecution
from config.common_config import ConfigManager
from utils.logger import logger
from classification.security_classifier import SecurityClassifier
import sast.sast_orchestrator
from patch_generation.patch_generator import PatchGenerator
from test_generation.test_generator import TestGenerator
from utils.issues_merger import JSONCombiner
from utils.plugin_json_converter import JsonPluginConverter
from utils.vscode_refresh import reload_vscode_window
import time

class WorkflowFramework:
    """
    A class that orchestrates the execution of various security analysis workflows.

    This framework integrates different components such as SAST (Static Application Security Testing),
    security classification, and symbolic execution to perform a comprehensive security analysis
    of a software project.

    The workflow is designed to run these components in a specific order, allowing for a
    structured approach to identifying and classifying potential security issues.
    """

    def __init__(self):
        self.config = ConfigManager.get_config()
        self.sast = sast.sast_orchestrator.SASTOrchestrator(self.config)
        self.security_classifier = SecurityClassifier(self.config)
        self.symbolic_execution = SymbolicExecution(self.config)
        self.patch_generator = PatchGenerator(self.config)
        # self.test_generator = TestGenerator(self.config)
        self.issues_merger = JSONCombiner(self.config)
        self.json_converter = JsonPluginConverter(self.config)

        

    def execute_workflow(self):
        logger.info("Starting workflow execution")
        start_time = time.time()
        self.sast.run_all()
        self.security_classifier.classify()
        self.symbolic_execution.analyze()
        self.issues_merger.run()
        self.patch_generator.main()
        self.json_converter.process()
        # self.test_generator.main()
        # reload_vscode_window(self.config)

        elapsed_time = time.time() - start_time
        logger.info(f"Workflow execution completed in {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    framework = WorkflowFramework()
    framework.execute_workflow()