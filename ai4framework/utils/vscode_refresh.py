import subprocess
from utils.logger import logger
import time

def reload_vscode_window(config):
    try:
        logger.warning('Please note that you should use the newly opened window for the settings to take effect.')
        time.sleep(2)
        subprocess.run(["code-server", config.get('DEFAULT', 'config.project_path'), "--reload-window"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to reload VSCode window: {e}")