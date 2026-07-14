"""Shared logging configuration for MediaSphere pipeline and API."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.constants import LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_PATH


def configure_pipeline_logging(
    log_file: Path | str | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure console + rotating-file logging for pipeline runners."""
    LOG_PATH.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if log_file:
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    root_logger.setLevel(level)
