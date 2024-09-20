import subprocess
import re
import os
import time
from utils.logger import logger

class Analyzer:
    """
    A class to run static analysis on a project using a specified analyzer tool.
    """

    def __init__(self, analyzer_path, project_name, project_path, results_path):
        """
        Initialize the Analyzer with project details and paths.

        Args:
            analyzer_path (str): Path to the analyzer tool executable.
            project_name (str): Name of the project to be analyzed.
            project_path (str): Path to the project's root directory.
            results_path (str): Path where analysis results will be stored.
        """
        self.analyzer = analyzer_path
        self.project_name = project_name
        self.project_path = project_path
        self.results_path = results_path
    
    def run_analysis(self):
        """
        Run the analysis on the specified project.

        This method executes the analyzer tool with the given project parameters,
        captures and logs the output, and returns the path to the generated JSON file.

        Returns:
            str: Path to the generated JSON file containing analysis results.

        Raises:
            Exception: If an error occurs during the analysis process.
        """
        logger.info(f"Analyzing project: {self.project_name}")

        # command = f'{self.analyzer} -projectName={self.project_name} -projectBaseDir={self.project_path} -resultsDir={self.results_path} -currentDate=now -runFB=false'
        command = (
        f'{self.analyzer} '
        f'-projectName={self.project_name} '
        f'-projectBaseDir={self.project_path} '
        f'-resultsDir={self.results_path} '
        f'-currentDate=now '
        f'-runFB=false '
        f'-runAndroidHunter=false '
        f'-runMetricHunter=false '
        f'-runDCF=false '
        f'-runVulnerabilityHunter=false '
        f'-runLIM2Patterns=false '
        f'-runFaultHunter=false '
        f'-runPMD=false'
    )
        start_time = time.time()
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
                bufsize=1
            )

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output.strip():
                    clean_output = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', '', output.strip())
                    logger.info(clean_output)

            stderr_output, _ = process.communicate()
            if stderr_output:
                for line in stderr_output.splitlines():
                    if line.strip():
                        clean_error = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', '', line.strip())
                        logger.error(clean_error)

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"Symbolic execution completed in {execution_time:.2f} seconds")

        json_file = os.path.join(self.results_path, self.project_name, 'java', 'now', f'{self.project_name}-RTEHunter.json')
        return json_file