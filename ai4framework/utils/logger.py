import logging
import os
from config.common_config import ConfigManager
from pathlib import Path

# Get configuration
config = ConfigManager.get_config()

# Define default log file path
AI4FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_FILE_PATH = AI4FRAMEWORK_DIR / 'logs' / 'ai4framework.log'

# Define ANSI color codes for different log levels
LOG_COLORS = {
    logging.DEBUG: "\033[94m",  # Blue
    logging.INFO: "\033[92m",   # Green
    logging.WARNING: "\033[93m",# Yellow
    logging.ERROR: "\033[91m",  # Red
    logging.CRITICAL: "\033[95m" # Magenta
}

RESET_COLOR = "\033[0m"  # Reset color

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Get the original log message
        message = super().format(record)

        # Apply the color based on the log level
        color = LOG_COLORS.get(record.levelno, RESET_COLOR)
        return f"{color}{message}{RESET_COLOR}"

def setup_logger(name, log_file=DEFAULT_LOG_FILE_PATH, file_level=logging.DEBUG, console_level=logging.INFO, filemode='w'):
    """
    Set up and configure a logger with different log levels for console and file handlers.

    Args:
        name (str): Name of the logger.
        log_file (str or Path): Path to the log file. Defaults to DEFAULT_LOG_FILE_PATH.
        file_level (int): Logging level for file handler. Defaults to logging.DEBUG.
        console_level (int): Logging level for console handler. Defaults to logging.INFO.
        filemode (str): File mode for opening the log file. Defaults to 'w' (write).

    Returns:
        logging.Logger: Configured logger object.
    """
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Define log format (same for file and console)
    formatter = logging.Formatter('%(asctime)s - %(module)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s')

    # Define colored formatter for console
    colored_formatter = ColoredFormatter('%(asctime)s - %(module)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s')

    # Set up file handler (log everything including DEBUG)
    file_handler = logging.FileHandler(log_file, mode=filemode)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(file_level)  # DEBUG level for the file

    # Set up console handler (log everything except DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(colored_formatter)
    console_handler.setLevel(console_level)  # INFO level for the console

    # Create and configure logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Overall logger level (doesn't affect individual handlers)

    # Add handlers if not already present
    if not logger.hasHandlers():
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Create a default logger
logger = setup_logger(__name__, console_level=logging.INFO)  # Console logs everything except DEBUG

def get_logger():
    """
    Get the default logger.

    Returns:
        logging.Logger: The default logger object.
    """
    return logger
