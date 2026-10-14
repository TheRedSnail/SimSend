"""
Logging Configuration Module
Provides unified logging management, outputting to both console and file

All application loggers live under the ``mirofish`` namespace. Handlers are
attached once, to the ``mirofish`` logger only; child loggers
(``mirofish.api``, ``mirofish.build``, ...) carry no handlers of their own and
propagate to it. That keeps exactly one file handler on ``mirofish.log``, so
midnight rotation can rename the file (several handlers holding the same file
open makes the rename fail on Windows).
"""

import os
import sys
import logging
import threading
from logging.handlers import TimedRotatingFileHandler

ROOT_LOGGER_NAME = 'mirofish'

# Log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')

_setup_lock = threading.Lock()


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


def _level_from_env() -> int:
    name = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level = logging.getLevelName(name)
    return level if isinstance(level, int) else logging.INFO


def setup_logger(name: str = ROOT_LOGGER_NAME, level: int = None) -> logging.Logger:
    """
    Configure the shared ``mirofish`` logger (idempotent).

    Args:
        name: Logger to return. Handlers are always attached to the
              ``mirofish`` root logger; any other name returns a child that
              propagates to it.
        level: Log level for the file handler and logger. Defaults to the
               ``LOG_LEVEL`` env var (INFO).

    Returns:
        The requested logger
    """
    root = logging.getLogger(ROOT_LOGGER_NAME)

    with _setup_lock:
        if not root.handlers:
            if level is None:
                level = _level_from_env()

            os.makedirs(LOG_DIR, exist_ok=True)

            root.setLevel(level)
            # Prevent logs from propagating to the Python root logger, avoiding
            # duplicate output.
            root.propagate = False

            detailed_formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            simple_formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s: %(message)s',
                datefmt='%H:%M:%S'
            )

            # File handler - rotates at midnight; delay=True defers opening the
            # file until the first record.
            file_handler = TimedRotatingFileHandler(
                os.path.join(LOG_DIR, 'mirofish.log'),
                when='midnight',
                backupCount=14,
                encoding='utf-8',
                delay=True,
            )
            file_handler.suffix = '%Y-%m-%d'
            file_handler.setLevel(level)
            file_handler.setFormatter(detailed_formatter)

            # Console handler - concise logs (INFO and above)
            _ensure_utf8_stdout()
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(max(level, logging.INFO))
            console_handler.setFormatter(simple_formatter)

            root.addHandler(file_handler)
            root.addHandler(console_handler)

    if name == ROOT_LOGGER_NAME:
        return root
    return get_logger(name)


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """
    Get a logger under the ``mirofish`` namespace.

    Names outside the namespace are nested under it so they share the single
    set of handlers.
    """
    if name != ROOT_LOGGER_NAME and not name.startswith(ROOT_LOGGER_NAME + '.'):
        name = f'{ROOT_LOGGER_NAME}.{name}'
    root = logging.getLogger(ROOT_LOGGER_NAME)
    if not root.handlers:
        setup_logger()
    logger = logging.getLogger(name)
    # Children never get their own handlers; they propagate to ``mirofish``.
    logger.propagate = True
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
