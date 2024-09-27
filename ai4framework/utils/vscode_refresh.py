import subprocess
from utils.logger import logger
import time

def reload_vscode_window(config):
    flag = 0
    try:
        logger.warning('Please note that you should use the newly opened vscode window for the settings to take effect.')
        time.sleep(2)
        subprocess.run(["code-server", config.get('DEFAULT', 'config.project_path'), "--reload-window"], check=True)
        flag = 1

    except subprocess.CalledProcessError as e:
        logger.warning(e)
        if flag == 0:
            print(f"Please re-run the previous Docker command without the 'bash' suffix to open VS Code in your browser. Once it's running, navigate to: http://localhost:8080/?folder={config.get('DEFAULT', 'config.project_path')}")