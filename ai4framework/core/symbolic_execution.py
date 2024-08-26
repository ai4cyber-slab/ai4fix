import subprocess
import re
from utils.logger import logger

class SymbolicExecution:
    def __init__(self, config):
        self.config = config
        self.project_name = self.config.get("DEFAULT", "config.project_name")
        self.project_path = self.config.get("DEFAULT", "config.project_path")
        self.results_path = self.config.get("ANALYZER", "config.analyzer_results_path")
        self.analyzer = self.config.get("ANALYZER", "config.analyzer")
    
    def analyze(self):
        logger.info(f"Analyzing project: {self.project_name}")

        commands = [
        f'{self.analyzer} -projectName={self.project_name} -projectBaseDir={self.project_path} -resultsDir={self.results_path} -currentDate=now -runFB=false -runAndroidHunter=false -runMetricHunter=false -runDCF=false -runMET=false -runVulnerabilityHunter=false -runMET=false -runLIM2Patterns=false -runFaultHunter=false -runPMD=false',
        f'cp {self.results_path}/{self.project_name}/java/now/{self.project_name}-RTEHunter.txt {self.results_path}/{self.project_name}/java/now/{self.project_name}-RTEHunter.json'
]

        command_string = ' && '.join(commands)
        
        try:
            process = subprocess.Popen(
                command_string,
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
                        clean_error = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', '', output.strip())
                        logger.error(clean_error)

        except Exception as e:
            logger.error(f"An error occurred: {e}")