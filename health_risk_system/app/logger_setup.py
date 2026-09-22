"""
logger_setup.py — Logging configuration for the health risk monitoring system.
"""

import logging
import logging.handlers
import os
from app.config import LOG_FILE, LOG_LEVEL


def setup_logging() -> None:
    """Configure root logger with file and (optional) console handlers."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # File handler — always active
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(fh)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
