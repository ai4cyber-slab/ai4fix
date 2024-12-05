import os
import sys
import time
import subprocess

from dotenv import load_dotenv, find_dotenv
from utils.logger import logger


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

    This class uses various LLMs to analyze and classify code changes
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
        self.api_key = self.config.get('API', 'config.key', fallback='')
        self.repo_path = self.config.get('DEFAULT', 'config.project_root')


    def classify(self):
        """
        Run the classification process.

        This method executes the external classifier script with the appropriate arguments
        and handles the output and potential errors.
        """
        # Check if the API key is available
        if self.api_key == '':
            logger.info("api key is not set. Skipping the classification process.")
            return
        
        # Check if the commit sha is available
        if self.config.get('DEFAULT', 'config.commit_sha') == '':
            logger.info("Commit sha is not set. Skipping the classification process.")
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_dir)
        command = [
            "python", "classifier.py",
            "-r", self.repo_path,
            "-f", self.config.get('DEFAULT', 'config.filter'),
            "-c", self.config.get('DEFAULT', 'config.commit_sha'),
            "-m", self.config.get('API', 'config.model'),
            "-t", self.config.get('API', 'config.temperature'),
            "-p", self.config.get('API', 'config.provider'),
            "-k", self.api_key
        ]

        try:
            logger.info("Classification started ...")
            start_time = time.time()

            with subprocess.Popen(
                command, cwd=find_script(os.curdir),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ) as process:
                stdout, stderr = process.communicate()

            end_time = time.time()
            elapsed_time = end_time - start_time

            if process.returncode == 0:
                logger.info("Classifier script executed successfully.")
                print(stdout.strip())
                logger.info(f"Classification completed in {elapsed_time:.2f} seconds")
            else:
                logger.error(f"Classifier script failed with return code {process.returncode}")
                logger.error(f"Error output: {stderr}")
                logger.error(f"Classification failed after {elapsed_time:.2f} seconds")

        except Exception as e:
            logger.error(f"An error occurred while running the classifier script: {str(e)}")
            logger.error(f"Classification process interrupted after {time.time() - start_time:.2f} seconds")
