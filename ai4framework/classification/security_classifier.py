from utils.logger import logger
import subprocess
from dotenv import load_dotenv, find_dotenv
import openai
import os
import time


def find_script(starting_directory):
    """
    Find the directory containing the 'classifier.py' script.

    Args:
        starting_directory (str): The directory to start searching from.

    Returns:
        str or None: The path to the directory containing 'classifier.py', or None if not found.
    """
    for root, dirs, files in os.walk(starting_directory):
        if 'classifier.py' in files:
            return root
    return None

class SecurityClassifier:
    """
    A class to handle security classification of code changes.

    This class uses OpenAI's GPT model to analyze and classify code changes
    for potential security impacts.
    """

    def __init__(self, config):
        """
        Initialize the SecurityClassifier.

        Args:
            config (ConfigParser): Configuration object containing necessary settings.
        """
        self.config = config
        dotenv_path = find_dotenv()
        load_dotenv(dotenv_path)
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.repo_path = self.config.get("DEFAULT", "config.project_path")

    def classify(self):
        """
        Run the classification process.

        This method executes the external classifier script with the appropriate arguments
        and handles the output and potential errors.
        """
        command = [
            "python", "classifier.py",
            "-r", self.repo_path,
            "-c", self.config.get('CLASSIFIER', 'commit_sha'),
            "-m", self.config.get('CLASSIFIER', 'gpt_model'),
            "-t", self.config.get('CLASSIFIER', 'temperature'),
            "-k", openai.api_key
        ]
        try:
            logger.info("Classification started ...")
            start_time = time.time()
            result = subprocess.run(command, cwd=find_script(os.curdir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result.returncode == 0:
                logger.info("Classifier script executed successfully.")
                logger.info(result.stdout)
                logger.info(f"Classification completed in {elapsed_time:.2f} seconds")
            else:
                logger.error("Classifier script failed with return code {}".format(result.returncode))
                logger.error("Error output:")
                logger.error(result.stderr)
                logger.error(f"Classification failed after {elapsed_time:.2f} seconds")
        except Exception as e:
            logger.error(f"An error occurred while running the classifier script: {e}")
            logger.error(f"Classification process interrupted after {time.time() - start_time:.2f} seconds")