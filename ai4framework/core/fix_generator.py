from utils.logger import logger

# todo: a certain file 'model_test_with_snippet.py' is mentioned in the flowchart but couldn't find it ai4fw repo.


class FixGenerator:
    def __init__(self, config):
        self.config = config

    def generate_fixes(self, issues_file):
        logger.info("Fix generation started")
        # todo: use the fakeAiFixCode.ts file to get the issues from sym execution and sast engine and generate the fixes
        # todo: receive the issues from the SAST engine too. (issues.json)
        # return patches