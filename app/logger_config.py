import logging
import sys

def create_logger(log_level: str = 'INFO', name: str = 'solar_monitor'):
    """
    Create and configure a logger for the entire application.
    Uses a single logger instance compatible with Home Assistant's logging system.
    
    Args:
        log_level: Log level string (CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET)
        name: Logger name
    
    Returns:
        Configured logger instance
    """
    VALID_LOG_LEVELS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
    
    level = log_level.upper()
    if level not in VALID_LOG_LEVELS:
        level = 'INFO'
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout,
        force=True
    )
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    return logger
