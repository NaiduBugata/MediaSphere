"""Run Lokal and YouTube pipelines on a shared schedule."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import lokal_collector
from run_lokal_analysis import configure_logging as configure_lokal_logging, run_cycle as run_lokal_cycle
from run_youtube_analysis import run_cycle as run_youtube_cycle
from youtube import config as yt_config

logger = logging.getLogger("run_all_pipelines")


def configure_logging() -> None:
    configure_lokal_logging()


def _merge_stats(lokal: dict[str, Any], youtube: dict[str, Any]) -> dict[str, Any]:
    errors = list(lokal.get("errors") or []) + list(youtube.get("errors") or [])
    return {
        "articles_fetched": int(lokal.get("articles_fetched") or 0) + int(youtube.get("articles_fetched") or 0),
        "duplicates": int(lokal.get("duplicates") or 0) + int(youtube.get("duplicates") or 0),
        "inserted": int(lokal.get("inserted") or 0) + int(youtube.get("inserted") or 0),
        "lokal_processed": int(lokal.get("total") or lokal.get("articles_fetched") or 0),
        "youtube_processed": int(youtube.get("total") or youtube.get("articles_fetched") or 0),
        "errors": errors,
        "lokal": lokal,
        "youtube": youtube,
    }


def run_combined_cycle() -> tuple[int, dict[str, Any]]:
    """
    Execute Lokal then YouTube once.

    Returns:
        (exit_code, aggregated_stats)
    """
    logger.info("=" * 60)
    logger.info("COMBINED PIPELINE CYCLE START")
    logger.info("=" * 60)

    logger.info("Collecting Lokal")
    lokal_code, lokal_stats = run_lokal_cycle()
    if lokal_code != 0:
        logger.warning("Lokal cycle finished with exit code %s", lokal_code)

    youtube_code = 0
    youtube_stats: dict[str, Any] = {
        "inserted": 0,
        "duplicates": 0,
        "articles_fetched": 0,
        "total": 0,
        "errors": [],
    }
    if yt_config.YOUTUBE_ENABLED:
        logger.info("Collecting YouTube")
        youtube_code, youtube_stats = run_youtube_cycle()
        if youtube_code != 0:
            logger.warning("YouTube cycle finished with exit code %s", youtube_code)
    else:
        logger.info("YouTube pipeline disabled; skipping.")

    stats = _merge_stats(lokal_stats, youtube_stats)
    exit_code = 0 if lokal_code == 0 and youtube_code == 0 else 1

    logger.info(
        "COMBINED PIPELINE CYCLE END | exit=%s | inserted=%s | duplicates=%s | fetched=%s",
        exit_code,
        stats["inserted"],
        stats["duplicates"],
        stats["articles_fetched"],
    )
    logger.info("=" * 60)
    return exit_code, stats


def run_forever() -> int:
    interval = lokal_collector.CHECK_INTERVAL
    logger.info(
        "Combined pipeline started | interval: %s seconds (%s hours)",
        interval,
        interval / 3600,
    )
    try:
        while True:
            run_combined_cycle()
            next_run = datetime.now(timezone.utc) + timedelta(seconds=interval)
            logger.info("Next combined run at %s UTC", next_run.isoformat())
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Combined pipeline stopped by user")
        return 0


def main() -> int:
    configure_logging()
    if "--once" in sys.argv:
        code, _stats = run_combined_cycle()
        return code
    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
