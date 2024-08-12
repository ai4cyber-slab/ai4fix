from utils.logger import logger
import subprocess
from dotenv import load_dotenv, find_dotenv
import openai
import os


def find_script(starting_directory):
    for root, dirs, files in os.walk(starting_directory):
        if 'classifier.py' in files:
            return root
    return None

class SecurityClassifier:
    def __init__(self, config):
        self.config = config
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')

    def classify(self, repo_path):
        command = [
            "python", "classifier.py",
            "-r", repo_path,
            "-c", self.config.get('CLASSIFIER', 'commit_sha'),
            "-m", self.config.get('CLASSIFIER', 'gpt_model'),
            "-t", self.config.get('CLASSIFIER', 'temperature'),
            "-k", openai.api_key
        ]
        starting_directory = os.path.dirname(os.path.abspath('..'))
        classifier_directory = find_script(starting_directory)
        try:
            result = subprocess.run(command, cwd=classifier_directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                logger.info("Classifier script executed successfully.")
                logger.info(result.stdout)
            else:
                logger.error("Classifier script failed with return code {}".format(result.returncode))
                logger.error("Error output:")
                logger.error(result.stderr)
        except Exception as e:
            logger.error(f"An error occurred while running the classifier script: {e}")