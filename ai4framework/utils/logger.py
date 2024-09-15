import logging
import os
from config.common_config import ConfigManager
from pathlib import Path

# Get configuration
config = ConfigManager.get_config()

# Define default log file path
# DEFAULT_LOG_FILE_PATH = "./logs/ai4framework.log"
AI4FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_FILE_PATH = AI4FRAMEWORK_DIR / 'logs' / 'ai4framework.log'

def setup_logger(name, log_file=DEFAULT_LOG_FILE_PATH, level=logging.DEBUG, filemode='w'):
    """
    Set up and configure a logger.

    Args:
        name (str): Name of the logger.
        log_file (str or Path): Path to the log file. Defaults to DEFAULT_LOG_FILE_PATH.
        level (int): Logging level. Defaults to logging.DEBUG.
        filemode (str): File mode for opening the log file. Defaults to 'w' (write).

    Returns:
        logging.Logger: Configured logger object.
    """
    # if not os.path.exists(os.path.dirname(log_file)):
    #     os.makedirs(os.path.dirname(log_file))
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Define log format
    formatter = logging.Formatter('%(asctime)s - %(module)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s')
    
    # Set up file handler
    handler = logging.FileHandler(log_file, mode=filemode)
    handler.setFormatter(formatter)

    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Create and configure logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Add handlers if not already present
    if not logger.hasHandlers():
        logger.addHandler(handler)
        logger.addHandler(console_handler)

    return logger

# Create a default logger
logger = setup_logger(__name__)

def get_logger():
    """
    Get the default logger.

    Returns:
        logging.Logger: The default logger object.
    """
    return logger
