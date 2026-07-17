"""Shared utilities — logging setup and common helpers."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import Settings, load_settings

_CONFIGURED = False


def setup_logging(settings: Settings | None = None) -> logging.Logger:
    """Configure application-wide logging to console and rotating file.

    Idempotent: safe to call multiple times; only configures handlers once.

    Args:
        settings: Optional settings instance. Loaded from env if omitted.

    Returns:
        The root application logger named ``telegram_scraper``.
    """
    global _CONFIGURED

    cfg = settings or load_settings()
    logger = logging.getLogger("telegram_scraper")
    logger.setLevel(getattr(logging, cfg.log_level, logging.INFO))

    if _CONFIGURED:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        cfg.log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, cfg.log_level, logging.INFO))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, cfg.log_level, logging.INFO))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _CONFIGURED = True
    logger.debug("Logging configured: level=%s file=%s", cfg.log_level, cfg.log_file)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the application namespace.

    Args:
        name: Optional submodule name (e.g. ``scraper`` → ``telegram_scraper.scraper``).

    Returns:
        A configured logger instance.
    """
    if name:
        return logging.getLogger(f"telegram_scraper.{name}")
    return logging.getLogger("telegram_scraper")
