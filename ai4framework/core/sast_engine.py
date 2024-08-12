import subprocess
import json
import os
import re
from utils.logger import logger

class SASTEngine:
    def __init__(self, config):
        self.config = config

    def analyze(self, source_code_path):
        logger.info("Analyzing source code with SAST tools: SpotBugs")
        
        if os.name == 'nt':  # Windows
            config_file_path = 'C:\\Users\\HP\\slab\\ai4fix\\ai4framework\\config\\config.properties'
            jar_path = 'C:\\Users\\HP\\slab\\ai4fix\\target\\AIFix4SecCode-1.0-SNAPSHOT.jar'
            _cwd = 'C:\\Users\\HP\\Music\\demo'
        else:  # Assume Linux
            config_file_path = '/mnt/c/Users/HP/slab/ai4fix/ai4framework/config/config_mnt.properties'
            jar_path = '/mnt/c/Users/HP/slab/ai4fix/target/AIFix4SecCode-1.0-SNAPSHOT.jar'
            _cwd = '/mnt/c/Users/HP/Music/demo'

        java_command = [
            'java',
            '-cp',
            jar_path,
            'eu.assuremoss.VulnerabilityRepairDriver',
            f"-config={config_file_path}"
        ]

        try:
            process = subprocess.Popen(
                java_command,
                cwd=_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    match = re.search(r"^\[?\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\]?\s*(.*)", output)
                    if match:
                        log_message = match.group(1).strip()
                        if log_message:
                            logger.info(log_message)

            stderr_output, _ = process.communicate()
            if stderr_output:
                for line in stderr_output.splitlines():
                    match = re.search(r"^\[?\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\]?\s*(.*)", line)
                    if match:
                        log_message = match.group(1).strip()
                        if log_message:
                            logger.error(log_message)

        except Exception as e:
            logger.error(f"An error occurred: {e}")

# if __name__ == '__main__':
#     sast_engine = SASTEngine({})
#     sast_engine.analyze('Demo')
