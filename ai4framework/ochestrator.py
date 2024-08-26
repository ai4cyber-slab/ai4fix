from core.security_classifier import SecurityClassifier
from core.symbolic_execution import SymbolicExecution
from config.common_config import ConfigManager
from utils.logger import logger

class WorkflowFramework:
    def __init__(self):
        self.config = ConfigManager.get_config()
        # self.sast = sast.sast_orchestrator.SASTOrchestrator(self.config)

        # self.security_classifier = SecurityClassifier(self.config)
        # self.security_annotator = SecurityAnnotator(self.config)
        # self.fix_generator = FixGenerator(self.config)

        self.symbolic_execution = SymbolicExecution(self.config)

    def execute_workflow(self):
        logger.info("Starting workflow execution")
        # self.sast.run_all()
        # classified_code = self.security_classifier.classify(project_path)
        # annotated_code = self.security_annotator.annotate(classified_code)
        # issues_file = self.symbolic_executor.execute(annotated_code)

        # self.sast_engine.analyze()
        self.symbolic_execution.analyze()

        logger.info("Workflow execution completed")
        pass


if __name__ == "__main__":
    framework = WorkflowFramework()
    framework.execute_workflow()