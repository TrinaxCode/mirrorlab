"""Tiny logging helper so MirrorLab never fights the host application's config."""

from __future__ import annotations

import logging
import os
import sys
from typing import ClassVar, Dict

__all__ = ["LOG_FORMAT", "get_logger", "setup_logging"]

LOG_FORMAT = "%(asctime)s │ %(levelname)-7s │ %(name)-22s │ %(message)s"
DATE_FORMAT = "%H:%M:%S"

_CONFIGURED = False


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


class _ColorFormatter(logging.Formatter):
    """Adds ANSI colours when stderr is a TTY."""

    COLORS: ClassVar[Dict[str, str]] = {
        "DEBUG": "\033[38;5;245m",
        "INFO": "\033[38;5;80m",
        "WARNING": "\033[38;5;214m",
        "ERROR": "\033[38;5;203m",
        "CRITICAL": "\033[48;5;203;38;5;231m",
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool) -> None:
        super().__init__(LOG_FORMAT, DATE_FORMAT)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not self.use_color:
            return text
        color = self.COLORS.get(record.levelname, "")
        return f"{color}{text}{self.RESET}" if color else text


def setup_logging(level: str | int = "INFO", force: bool = False) -> None:
    """Configure the root ``mirrorlab`` logger exactly once."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    logger = logging.getLogger("mirrorlab")
    logger.setLevel(level if isinstance(level, int) else str(level).upper())
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_ColorFormatter(_supports_color()))
    logger.handlers[:] = [handler]
    logger.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child of the ``mirrorlab`` logger."""
    setup_logging()
    return logging.getLogger(f"mirrorlab.{name}" if not name.startswith("mirrorlab") else name)
