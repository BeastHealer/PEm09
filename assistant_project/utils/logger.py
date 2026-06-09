"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Optional

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger once for the entire application."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)

    # Reduce noise from third-party libraries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a named logger, ensuring logging is configured."""
    from utils.config import get_settings

    setup_logging(get_settings().log_level)
    return logging.getLogger(name or "assistant")
