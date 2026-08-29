"""Logging configuration for pytuiplayer."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None, log_file: Path | None = None) -> None:
    """Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
            Defaults to env var PYTUIP_LOG_LEVEL or INFO.
        log_file: Path to log file. Defaults to ~/.local/share/pytuiplayer/app.log
    """
    if level is None:
        level = os.getenv("PYTUIP_LOG_LEVEL", "INFO")
    
    if log_file is None:
        log_dir = Path.home() / ".local" / "share" / "pytuiplayer"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
    
    root_logger = logging.getLogger("pytuiplayer")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Avoid adding duplicate handlers
    if root_logger.handlers:
        return
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError):
        pass  # Silently skip file logging if not possible


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(f"pytuiplayer.{name}")
