"""Run Lokal and YouTube pipelines on a shared schedule."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta, timezone

import lokal_collector
from run_lokal_analysis import configure_logging as configure_lokal_logging, run_cycle as run_lokal_cycle
from run_youtube_analysis import run_cycle as run_youtube_cycle
from youtube import config as yt_config

logger = logging.getLogger("run_all_pipelines")


def configure_logging() -> None:
    configure_lokal_logging()


def run_combined_cycle() -> int:
    logger.info("=" * 60)
    logger.info("COMBINED PIPELINE CYCLE START")
    logger.info("=" * 60)

    lokal_code = run_lokal_cycle()
    if lokal_code != 0:
        logger.warning("Lokal cycle finished with exit code %s", lokal_code)

    youtube_code = 0
    if yt_config.YOUTUBE_ENABLED:
        youtube_code = run_youtube_cycle()
        if youtube_code != 0:
            logger.warning("YouTube cycle finished with exit code %s", youtube_code)
    else:
        logger.info("YouTube pipeline disabled; skipping.")

    logger.info("=" * 60)
    logger.info("COMBINED PIPELINE CYCLE END")
    logger.info("=" * 60)
    return 0 if lokal_code == 0 and youtube_code == 0 else 1


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
        return run_combined_cycle()
    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
