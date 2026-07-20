"""Lokal collector orchestration: fetch, dedupe, save, and scheduled loop."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from sources.base.constituency_validator import filter_articles_by_constituency
from sources.lokal.api import create_session
from sources.lokal.config import CHECK_INTERVAL
from sources.lokal.constants import (
    COLLECTOR_NAME,
    LOOKBACK_HOURS,
    OUTPUT_DIRECTORY,
    OUTPUT_FILENAME,
    SOURCE_URL,
    TAG_ID,
)
from sources.lokal.extractor import fetch_last_24hr_news
from sources.lokal.normalizer import remove_duplicates

logger = logging.getLogger("lokal_collector")


def get_output_path() -> Path:
    """
    Resolve the JSON output file path.

    Returns:
        Path object for the output JSON file.
    """
    return Path(OUTPUT_DIRECTORY) / OUTPUT_FILENAME


def save_json(articles: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Save collected articles to a structured JSON file.

    Purpose:
        Persist the collector envelope and article list with UTF-8 Telugu support.

    Parameters:
        articles: Deduplicated normalized article list.
        output_path: Destination JSON file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collector": COLLECTOR_NAME,
        "source": SOURCE_URL,
        "tag_id": TAG_ID,
        "lookback_hours": LOOKBACK_HOURS,
        "total_articles": len(articles),
        "articles": articles,
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    logger.info("Saved %s articles to %s", len(articles), output_path)


def run() -> None:
    """
    Execute one full collector cycle.

    Purpose:
        Fetch recent news, deduplicate, save JSON, and log execution metrics
        without terminating the scheduler on recoverable errors.
    """
    started_at = time.perf_counter()
    logger.info("Collector cycle started")

    try:
        session = create_session()
        raw_articles = fetch_last_24hr_news(session)
        articles, duplicates_removed = remove_duplicates(raw_articles)
        articles, constituency_rejected = filter_articles_by_constituency(
            articles,
            source_label="lokal",
        )
        output_path = get_output_path()
        save_json(articles, output_path)

        elapsed = time.perf_counter() - started_at
        logger.info("Duplicates removed: %s", duplicates_removed)
        logger.info("Constituency rejected: %s", constituency_rejected)
        logger.info("Total saved: %s", len(articles))
        logger.info("Execution time: %.2f seconds", elapsed)
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        logger.exception("Collector cycle failed after %.2f seconds: %s", elapsed, exc)


def configure_logging() -> None:
    """Configure module logging for standalone scheduled runs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> None:
    """Start the scheduled collector loop (standalone mode)."""
    configure_logging()
    logger.info("Lokal News Collector started")

    while True:
        run()
        logger.info("Sleeping for %s seconds (%s hours)", CHECK_INTERVAL, CHECK_INTERVAL / 3600)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
