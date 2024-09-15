from symbolic_execution.execution import SymbolicExecution
from config.common_config import ConfigManager
from utils.logger import logger
from classification.security_classifier import SecurityClassifier
import sast.sast_orchestrator

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
        

    def execute_workflow(self):
        logger.info("Starting workflow execution")
        self.sast.run_all()
        self.security_classifier.classify()
        self.symbolic_execution.analyze()

        logger.info("Workflow execution completed")
        pass


if __name__ == "__main__":
    framework = WorkflowFramework()
    framework.execute_workflow()