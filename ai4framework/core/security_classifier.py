from utils.logger import logger

class SecurityClassifier:
    def __init__(self, config):
        self.config = config

    def classify(self, source_code_path):
        logger.debug("Classifying security level")
        classified_code = f"Classified code from {source_code_path}"
        # todo: call the security classifier tool coming from the Python LLM made by ESZTER
        #  (belongs to AI4VULN Component)
        #   this should return a result in the form (TBD)
        return classified_code