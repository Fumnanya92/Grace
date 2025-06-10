from logging_config import configure_logger

logger = configure_logger("test_module")

logger.debug("This is a DEBUG log.")
logger.info("This is an INFO log.")
logger.warning("This is a WARNING log.")
logger.error("This is an ERROR log.")
logger.critical("This is a CRITICAL log.")
