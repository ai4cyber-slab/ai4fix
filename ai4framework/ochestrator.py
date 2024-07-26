from core.security_classifier import SecurityClassifier
from config.common_config import ConfigManager
from utils.logger import logger

class WorkflowFramework:
    def __init__(self):
        self.config = ConfigManager.get_config()
        self.security_classifier = SecurityClassifier(self.config)
        # self.security_annotator = SecurityAnnotator(self.config)
        # self.symbolic_executor = SymbolicExecutor(self.config)
        # self.fix_generator = FixGenerator(self.config)
        # self.sast_engine = SASTEngine(self.config)
        # self.test_generator = TestGenerator(self.config)
        # self.verifier = Verifier(self.config)
        # self.sorter = Sorter(self.config)
        # self.orchestration_and_logging = OrchestrationAndLogging(self.config)

    def execute_workflow(self, source_code_path):
        logger.info("Starting workflow execution")
        classified_code = self.security_classifier.classify(source_code_path)
        # annotated_code = self.security_annotator.annotate(classified_code)
        # issues_file = self.symbolic_executor.execute(annotated_code)
        logger.info("Workflow execution completed")


if __name__ == "__main__":
    # source_code_path = ConfigManager.get_config()['source_code_path']
    framework = WorkflowFramework()
    framework.execute_workflow(None)
