"""
Logger module for the Watcher application.
Provides debug logging functionality with optional verbosity control.
"""

import os
import sys
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('watcher.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Global debug flag (set via environment variable WATCHER_DEBUG=1)
DEBUG_ENABLED = os.getenv('WATCHER_DEBUG', '0').lower() in ('1', 'true', 'yes')

def debug(message):
    """Log debug messages if DEBUG_ENABLED is True."""
    if DEBUG_ENABLED:
        logging.getLogger().debug(message)

def info(message):
    """Log info messages."""
    logging.getLogger().info(message)

def warning(message):
    """Log warning messages."""
    logging.getLogger().warning(message)

def error(message):
    """Log error messages."""
    logging.getLogger().error(message)

def critical(message):
    """Log critical messages."""
    logging.getLogger().critical(message)

# Example usage:
# debug("This is a debug message")
# info("This is an info message")
# warning("This is a warning message")
# error("This is an error message")
# critical("This is a critical message")