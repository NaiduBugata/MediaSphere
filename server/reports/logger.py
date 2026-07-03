"""Shared logger for the daily report feature."""

from __future__ import annotations

import logging


def get_logger(name: str = "reports") -> logging.Logger:
    """Return a namespaced logger, configuring a default handler once."""
    logger = logging.getLogger(name)
    if not logger.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
