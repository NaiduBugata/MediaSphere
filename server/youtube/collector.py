"""Orchestrate YouTube search, transcript fetch, and news filtering."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .clean import TranscriptCleaner
from .search import run_search
from .transcripts import run_collect

logger = logging.getLogger("youtube.collector")


def get_output_path() -> Path:
    return config.NEWS_JSON


def run(days: int | None = None) -> Path:
    """
    Run full YouTube collection: search → transcripts → clean → youtube_news.json.

    Returns:
        Path to the collector JSON envelope.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lookback = days if days is not None else config.YOUTUBE_SEARCH_PERIOD_DAYS

    run_search(days=lookback)
    transcripts = run_collect()

    cleaner = TranscriptCleaner()
    articles = []
    news_count = 0
    filtered_count = 0

    for item in transcripts:
        transcript = item.get("transcript", "")
        if len(transcript) < config.YOUTUBE_MIN_CONTENT_CHARS:
            continue

        result = cleaner.clean(transcript, item.get("title", ""), item.get("channel", ""))
        if not result["is_news"] or len(result["clean_text"]) < config.YOUTUBE_MIN_CONTENT_CHARS:
            filtered_count += 1
            continue

        video_id = item["video_id"]
        articles.append({
            "id": video_id,
            "video_id": video_id,
            "title": item.get("title", ""),
            "content": result["clean_text"],
            "channel": item.get("channel", ""),
            "url": item.get("url", ""),
            "created_on": item.get("published_at", ""),
        })
        news_count += 1

    envelope = {
        "source": "youtube",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback,
        "articles": articles,
    }

    with open(config.NEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    logger.info(
        "YouTube collector done | transcripts: %d | news: %d | filtered: %d | output: %s",
        len(transcripts),
        news_count,
        filtered_count,
        config.NEWS_JSON,
    )
    return config.NEWS_JSON
