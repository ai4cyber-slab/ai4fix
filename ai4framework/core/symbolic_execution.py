import subprocess
import re
from utils.logger import logger

class SymbolicExecution:
    def __init__(self, config):
        self.config = config
    
    def analyze(self, project):
        logger.info(f"Analyzing project: {project}")
        
        commands = [
            f'./Java/AnalyzerJava -projectName={project} -projectBaseDir={project} -resultsDir=Results -currentDate=now -runFB=false -runAndroidHunter=false -runMetricHunter=false -runDCF=false -runMET=false -runVulnerabilityHunter=false -runMET=false -runLIM2Patterns=false -runFaultHunter=false -runPMD=false',
            f'./Java/LinuxTools/GraphDump ./Results/{project}/java/now/analyzer/graph/{project}-RTEHunter.graph -json:./Results/{project}/java/now/analyzer/graph/{project}-RTEHunter.json'
        ]

        command_string = ' && '.join(commands)
        arch_cwd = '/mnt/c/Users/HP/Music/demo'
        
        try:
            process = subprocess.Popen(
                command_string,
                cwd=arch_cwd,
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
                    # Remove the timestamp from the output line
                    clean_output = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', '', output.strip())
                    logger.info(clean_output)

            stderr_output, _ = process.communicate()
            if stderr_output:
                for line in stderr_output.splitlines():
                    if line.strip():
                        # Remove the timestamp from the error line
                        clean_error = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', '', output.strip())
                        logger.error(clean_error)

        except Exception as e:
            logger.error(f"An error occurred: {e}")

# if __name__ == '__main__':
#     symbolic_execution = SymbolicExecution({})
#     symbolic_execution.analyze('Demo')
