import logging
import os
from config.common_config import ConfigManager


config = ConfigManager.get_config()
DEFAULT_LOG_FILE_PATH = "./logs/ai4framework.log"

def setup_logger(name, log_file=DEFAULT_LOG_FILE_PATH, level=logging.DEBUG, filemode='w'):

    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler(log_file, mode=filemode)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.hasHandlers():
        logger.addHandler(handler)

    return logger


logger = setup_logger('ai4framework')


def get_logger():
    return logger
