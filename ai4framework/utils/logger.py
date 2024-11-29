import logging
from pathlib import Path
import os

AI4FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_FILE_PATH = os.path.join(os.getenv('LOCAL_PROJECT_PATH'), '.ai4framework', 'logs', 'ai4framework.log')
BANNER_FILE_PATH = os.path.join(AI4FRAMEWORK_DIR, 'banner.txt')
LOG_COLORS = {
    logging.DEBUG: "\033[94m",  # Blue
    logging.INFO: "\033[92m",   # Green
    logging.WARNING: "\033[93m",# Yellow
    logging.ERROR: "\033[91m",  # Red
    logging.CRITICAL: "\033[95m" # Magenta
}

BANNER_COLOR = "\033[96m"
RESET_COLOR = "\033[0m"

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        color = LOG_COLORS.get(record.levelno, RESET_COLOR)
        return f"{color}{message}{RESET_COLOR}"

def setup_logger(name, log_file=DEFAULT_LOG_FILE_PATH, banner_file=BANNER_FILE_PATH, file_level=logging.DEBUG, console_level=logging.INFO, filemode='a'):
    """
    Set up and configure a logger with different log levels for console and file handlers.

    Args:
        name (str): Name of the logger.
        log_file (str or Path): Path to the log file. Defaults to DEFAULT_LOG_FILE_PATH.
        banner_file (str or Path): Path to the banner file.
        file_level (int): Logging level for file handler. Defaults to logging.DEBUG.
        console_level (int): Logging level for console handler. Defaults to logging.INFO.
        filemode (str): File mode for opening the log file. Defaults to 'a' (append).

    Returns:
        logging.Logger: Configured logger object.
    """
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    if not log_file.exists() and Path(banner_file).exists():
        with open(banner_file, 'r') as banner:
            banner_content = banner.read()
        with open(log_file, 'w') as f:
            f.write(banner_content + "\n")

        print(f"{BANNER_COLOR}{banner_content}{RESET_COLOR}")
        
    formatter = logging.Formatter('%(asctime)s - %(module)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s')
    colored_formatter = ColoredFormatter('%(asctime)s - %(module)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_file, mode=filemode)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(file_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)
    console_handler.setLevel(console_level)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.hasHandlers():
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logger(__name__, console_level=logging.INFO)

def get_logger():
    """
    Get the default logger.

    Returns:
        logging.Logger: The default logger object.
    """
    return logger
