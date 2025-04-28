import logging
from pathlib import Path
import os
from datetime import datetime
from tqdm import tqdm
from ai4test.ai4test_config import ai4test_dir

AI4TEST_DIR = ai4test_dir
DEFAULT_LOG_FILE_PATH = os.path.join(
    os.path.abspath(AI4TEST_DIR),
    "logs",
    f"ai4test-{datetime.now()}.log",
)
LOG_COLORS = {
    logging.DEBUG:    "\033[94m",  # Blue
    logging.INFO:     "\033[92m",  # Green
    logging.WARNING:  "\033[93m",  # Yellow
    logging.ERROR:    "\033[91m",  # Red
    logging.CRITICAL: "\033[95m",  # Magenta
}
BANNER_COLOR = "\033[96m"
RESET_COLOR  = "\033[0m"


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return f"{LOG_COLORS.get(record.levelno, RESET_COLOR)}{message}{RESET_COLOR}"


class TqdmHandler(logging.Handler):
    """Write log lines via tqdm.write() so active bars stay intact."""
    def __init__(self, level=logging.INFO):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logger(
    name,
    log_file=DEFAULT_LOG_FILE_PATH,
    file_level=logging.DEBUG,
    console_level=logging.INFO,
    filemode="a",
):
    """Create a logger with a file handler + tqdm‑safe console handler."""
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # formatters
    std_fmt     = "%(asctime)s - %(module)s - %(funcName)s - %(lineno)d - %(levelname)s - %(message)s"
    file_fmt    = logging.Formatter(std_fmt)
    color_fmt   = ColoredFormatter(std_fmt)

    # file handler
    file_h = logging.FileHandler(log_file, mode=filemode)
    file_h.setFormatter(file_fmt)
    file_h.setLevel(file_level)


    console_h = TqdmHandler(console_level)
    console_h.setFormatter(color_fmt)
    console_h.setLevel(console_level)

    # build / cache logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.hasHandlers():
        logger.addHandler(file_h)
        logger.addHandler(console_h)
        logger.propagate = False

    return logger



logger = setup_logger(__name__, console_level=logging.INFO)
