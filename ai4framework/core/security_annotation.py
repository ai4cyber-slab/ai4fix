from utils.logger import logger

class SecurityAnnotator:
    def __init__(self, config):
        self.config = config

    def annotate(self, classified_code):
        logger.info("Security annotation started")
        # todo: call the security annotation artifact.
        #   this should return a result in the form (TBD)
        # return annotated_code
