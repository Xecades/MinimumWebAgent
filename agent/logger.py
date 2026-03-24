import hashlib
import logging
import sys
from datetime import datetime
from pathlib import Path

import colorlog

_LOGS_DIR = Path("logs")


class _EscapeNewlinesFormatter(logging.Formatter):
    """Escapes newlines in all log records so each entry stays on one line."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return formatted.replace("\n", "\\n").replace("\r", "\\r")


class _ColorEscapeNewlinesFormatter(colorlog.ColoredFormatter):
    """Colored + escapes newlines in all log records."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return formatted.replace("\n", "\\n").replace("\r", "\\r")


_LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


def make_logger(session_id: str) -> logging.Logger:
    """Create a logger that writes to both stderr (colored) and a per-session log file."""
    _LOGS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_suffix = hashlib.sha1(session_id.encode()).hexdigest()[:8]
    log_path = _LOGS_DIR / f"{timestamp}.{hash_suffix}.log"

    logger = logging.getLogger(session_id)
    logger.setLevel(logging.DEBUG)

    # File handler: plain text, newlines escaped.
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        _EscapeNewlinesFormatter("%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%H:%M:%S")
    )

    # Stderr handler: colored, newlines escaped.
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        _ColorEscapeNewlinesFormatter(
            "%(log_color)s%(asctime)s [%(levelname)-8s]%(reset)s %(message)s",
            datefmt="%H:%M:%S",
            log_colors=_LOG_COLORS,
        )
    )

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.propagate = False

    logger.info("Log file: %s", log_path)
    return logger
