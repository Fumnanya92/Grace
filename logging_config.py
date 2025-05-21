import logging
import os
from logging.handlers import RotatingFileHandler

def configure_logger(module_name: str, log_dir: str = "logs", max_bytes: int = 1_000_000, backup_count: int = 3) -> logging.Logger:
    """
    Configure a rotating logger for a specific module.

    Args:
        module_name (str): Name of the module
        log_dir (str): Directory for log files (default: "logs")
        max_bytes (int): Max file size before rotation (default: 1MB)
        backup_count (int): Number of backup logs to keep (default: 3)

    Returns:
        logging.Logger: Configured logger
    """
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    # Rotating file handler
    log_file = os.path.join(log_dir, f"{module_name}.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
        mode='a'
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
