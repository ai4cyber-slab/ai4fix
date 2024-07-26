import subprocess

from logger import logger


def run_command(command):
    logger.info(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Error running command: {command}\n{result.stderr}")
        raise Exception(f"Command failed: {command}")
    logger.debug(f"Command output: {result.stdout}")
    return result.stdout


if __name__ == '__main__':
    print(run_command("pwd"))