"""Rotating file logging for Sumo.

We log wake events, API errors, and lifecycle events -- enough to debug why a
wake word was missed or an API call failed -- but NOT conversation content
unless ``log_conversation`` is explicitly enabled in config. Nothing secret
(the API key) is ever passed to the logger.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


class EventLogger:
    """Thin wrapper so call sites read as ``log.event("wake_detected", ...)``
    rather than fiddling with logging levels everywhere."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def event(self, event_type: str, detail: str = "") -> None:
        self._logger.info("%s | %s", event_type, detail)

    def warn(self, event_type: str, detail: str = "") -> None:
        self._logger.warning("%s | %s", event_type, detail)

    def error(self, event_type: str, detail: str = "") -> None:
        self._logger.error("%s | %s", event_type, detail)


def setup_logging(
    log_path: str,
    level: str = "INFO",
    max_bytes: int = 1_000_000,
    backups: int = 3,
) -> EventLogger:
    directory = os.path.dirname(log_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    logger = logging.getLogger("sumo")
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.propagate = False

    # Avoid duplicate handlers if setup is called more than once.
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)

    return EventLogger(logger)
