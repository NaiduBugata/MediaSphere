"""Collector manager: runs all enabled collectors in sequence."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from collectors.base.registry import enabled_collectors

logger = logging.getLogger("collectors.manager")


def run_all_collectors() -> dict[str, dict[str, Any]]:
    """
    Run every enabled collector and return results keyed by source name.

    Each result dict contains 'articles', 'path', 'duration', 'error'.
    """
    results: dict[str, dict[str, Any]] = {}

    for name, cls in enabled_collectors():
        started = time.perf_counter()
        try:
            collector = cls()
            articles = collector.collect()
            duration = time.perf_counter() - started
            results[name] = {
                "articles": articles,
                "count": len(articles),
                "duration": round(duration, 3),
                "error": None,
            }
            logger.info("Collector %s: %d articles in %.2fs", name, len(articles), duration)
        except Exception as exc:
            duration = time.perf_counter() - started
            logger.error("Collector %s failed after %.2fs: %s", name, duration, exc)
            results[name] = {
                "articles": [],
                "count": 0,
                "duration": round(duration, 3),
                "error": str(exc),
            }

    return results
