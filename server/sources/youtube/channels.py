"""YouTube Data API search for constituency keywords across channels."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from sources.youtube import config

logger = logging.getLogger("youtube.search")


def to_rfc3339(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def search_videos(
    youtube,
    query: str,
    published_after: str,
    published_before: str,
    max_results: int,
) -> list[dict]:
    try:
        response = (
            youtube.search()
            .list(
                q=query,
                part="snippet",
                maxResults=max_results,
                type="video",
                publishedAfter=published_after,
                publishedBefore=published_before,
                order="date",
            )
            .execute()
        )
        results = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            results.append({
                "video_id": video_id,
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })
        return results
    except Exception as exc:
        logger.error("YouTube API error for keyword '%s': %s", query, exc)
        return []


def run_search(days: int | None = None) -> list[dict]:
    """Search YouTube and save unique videos to videos.json."""
    if not config.YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY is not set")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lookback = days if days is not None else config.YOUTUBE_SEARCH_PERIOD_DAYS
    now = datetime.now(tz=timezone.utc)
    published_after = to_rfc3339(now - timedelta(days=lookback))
    published_before = to_rfc3339(now)

    logger.info("Searching YouTube from %s to %s", published_after, published_before)
    youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)

    all_videos: list[dict] = []
    seen: set[str] = set()

    for keyword in config.KEYWORDS:
        results = search_videos(
            youtube,
            keyword,
            published_after,
            published_before,
            config.YOUTUBE_MAX_RESULTS_PER_KEYWORD,
        )
        new_count = 0
        for video in results:
            if video["video_id"] not in seen:
                seen.add(video["video_id"])
                all_videos.append(video)
                new_count += 1
        logger.info("Keyword '%s' | found %d | cumulative %d", keyword, new_count, len(all_videos))

    with open(config.VIDEOS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_videos, f, ensure_ascii=False, indent=2)

    logger.info("Search complete: %d unique videos", len(all_videos))
    return all_videos
