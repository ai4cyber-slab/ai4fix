import json
from utils.logger import logger

class TestGenerator:
    def __init__(self, config):
        self.config = config

    def generate_tests(self, issues_file):
        logger.info("Test generation started")


        try:
            with open(issues_file, 'r') as file:
                issues = json.load(file)
        except Exception as e:
            logger.error("Failed to load issues file: %s", e)
            return None


        tests = self.create_tests_from_issues(issues)

        tests_file = self.config.get('General', 'config.results_path') + '/generated_tests.json'
        try:
            with open(tests_file, 'w') as file:
                json.dump(tests, file, indent=4)
            logger.info("Test generation completed successfully. Tests saved to %s", tests_file)
        except Exception as e:
            logger.error("Failed to save generated tests: %s", e)
            return None

        return tests_file

    # def create_tests_from_issues(self, issues):
    #     return tests
