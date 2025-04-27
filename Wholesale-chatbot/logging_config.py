import logging
import os

def configure_logger(module_name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Configure a logger for a specific module.

    Args:
        module_name (str): The name of the module.
        log_dir (str): The directory where log files will be stored.

    Returns:
        logging.Logger: Configured logger for the module.
    """
    # Ensure the log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Create a logger
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    # Create a file handler for the module
    log_file = os.path.join(log_dir, f"{module_name}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    # Create a console handler for the module
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Create a formatter and add it to both handlers
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    if not logger.handlers:  # Avoid adding multiple handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

def clear_log_file(module_name: str, log_dir: str = "logs") -> None:
    """
    Clear the contents of the log file for a specific module.

    Args:
        module_name (str): The name of the module.
        log_dir (str): The directory where log files are stored.
    """
    log_file = os.path.join(log_dir, f"{module_name}.log")
    if os.path.exists(log_file):
        with open(log_file, "w") as file:
            file.truncate(0)  # Clear the file contents
        print(f"Log file '{log_file}' has been cleared.")
    else:
        print(f"Log file '{log_file}' does not exist.")