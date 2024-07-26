from utils.logger import logger

class SymbolicExecutor:
    def __init__(self, config):
        self.config = config

    def execute(self, annotated_code):
        logger.info("Symbolic execution started")
        # todo: call the symbolic execution (Java App provided by FEA)
        #   this should return the identified issues as : issues.json, the form (TBD)
        pass