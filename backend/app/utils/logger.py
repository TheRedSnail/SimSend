"""
Logging Configuration Module
Provides unified logging management, outputting to both console and file
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


def _ensure_utf8_stdout():
    """
    Ensure stdout/stderr use UTF-8 encoding
    Fixes encoding issues on Windows console
    """
    if sys.platform == 'win32':
        # Reconfigure standard output to UTF-8 on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# Log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'mirofish', level: int = logging.DEBUG) -> logging.Logger:
    """
    Set up a logger

    Args:
        name: Logger name
        level: Log level

    Returns:
        Configured logger
    """
    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent logs from propagating to the root logger, avoiding duplicate output
    logger.propagate = False

    # If handlers already exist, don't add duplicates
    if logger.handlers:
        return logger

    # Log format
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # 1. File handler - rotates at midnight so a long-lived process moves to a
    #    fresh dated file each day. (The previous RotatingFileHandler baked the
    #    startup date into the filename, so the process kept writing to that one
    #    day's file forever.)
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, 'mirofish.log'),
        when='midnight',
        backupCount=14,
        encoding='utf-8'
    )
    file_handler.suffix = '%Y-%m-%d'
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # 2. Console handler - Concise logs (INFO and above)
    # Ensure UTF-8 encoding on Windows to avoid garbled characters
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = 'mirofish') -> logging.Logger:
    """
    Get a logger (creates one if it doesn't exist)

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# Create default logger
logger = setup_logger()


# Convenience methods
def debug(msg: str, *args, **kwargs) -> None:
    logger.debug(msg, *args, **kwargs)

def info(msg: str, *args, **kwargs) -> None:
    logger.info(msg, *args, **kwargs)

def warning(msg: str, *args, **kwargs) -> None:
    logger.warning(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs) -> None:
    logger.error(msg, *args, **kwargs)

def critical(msg: str, *args, **kwargs) -> None:
    logger.critical(msg, *args, **kwargs)
