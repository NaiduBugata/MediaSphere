"""
search_youtube.py — Stage 1: YouTube Search
Enhanced with date-range filtering, CLI args, config integration, and structured logging.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

import config

# ── Logging setup ──────────────────────────────────────────────────────────────
os.makedirs(config.DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [search] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.PIPELINE_LOG, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Date helpers ───────────────────────────────────────────────────────────────

def parse_date(date_str: str) -> datetime:
    """Parse YYYY-MM-DD string to UTC-aware datetime."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.error("Invalid date format '%s'. Expected YYYY-MM-DD.", date_str)
        sys.exit(1)


def to_rfc3339(dt: datetime) -> str:
    """Convert datetime to RFC3339 string required by YouTube API."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_date_range(args) -> tuple[str, str]:
    """Return (published_after, published_before) RFC3339 strings."""
    now = datetime.now(tz=timezone.utc)

    if args.start_date and args.end_date:
        start = parse_date(args.start_date)
        end = parse_date(args.end_date).replace(hour=23, minute=59, second=59)
        if start > end:
            logger.error("--start-date '%s' is later than --end-date '%s'.", args.start_date, args.end_date)
            sys.exit(1)
        return to_rfc3339(start), to_rfc3339(end)

    if args.start_date:
        start = parse_date(args.start_date)
        return to_rfc3339(start), to_rfc3339(now)

    if args.end_date:
        end = parse_date(args.end_date).replace(hour=23, minute=59, second=59)
        period = timedelta(days=config.SEARCH_PERIOD_DAYS)
        return to_rfc3339(end - period), to_rfc3339(end)

    # Default: last N days
    days = args.days if args.days else config.SEARCH_PERIOD_DAYS
    start = now - timedelta(days=days)
    return to_rfc3339(start), to_rfc3339(now)


# ── Search logic ───────────────────────────────────────────────────────────────

def search_videos(youtube, query: str, published_after: str, published_before: str,
                  max_results: int) -> list[dict]:
    """Execute a single YouTube search and return list of video dicts."""
    try:
        request = youtube.search().list(
            q=query,
            part="snippet",
            maxResults=max_results,
            type="video",
            publishedAfter=published_after,
            publishedBefore=published_before,
            order="date"
        )

        response = request.execute()
        results = []
        for item in response.get("items", []):
            results.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            })
        return results
    except Exception as exc:
        logger.error("YouTube API error for keyword '%s': %s", query, exc)
        return []


def run_search(args=None) -> list[dict]:
    """Main search function. Returns list of video records."""
    parser = argparse.ArgumentParser(description="Telugu News Pipeline — Stage 1: YouTube Search")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, help="Number of past days to search (default: 10)")
    parser.add_argument("--skip-cache", action="store_true", help="Overwrite existing videos.json")

    parsed = parser.parse_args(args)

    # Validate --days
    if parsed.days is not None and parsed.days < 1:
        logger.error("--days must be a positive integer (≥1), got %d.", parsed.days)
        sys.exit(1)

    published_after, published_before = compute_date_range(parsed)
    logger.info("Searching videos from %s to %s", published_after, published_before)

    youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)

    all_videos: list[dict] = []
    seen: set[str] = set()
    cumulative = 0

    for keyword in config.KEYWORDS:
        results = search_videos(
            youtube, keyword, published_after, published_before,
            config.MAX_RESULTS_PER_KEYWORD
        )
        new_count = 0
        for video in results:
            if video["video_id"] not in seen:
                seen.add(video["video_id"])
                all_videos.append(video)
                new_count += 1
        cumulative += new_count
        logger.info("Keyword: '%-20s' | Found: %2d | Cumulative total: %d",
                    keyword, new_count, cumulative)

    # Save — always overwrite when run standalone
    out_path = config.VIDEOS_JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_videos, f, ensure_ascii=False, indent=2)

    logger.info("Stage 1 complete: %d unique videos saved to %s", len(all_videos), out_path)
    return all_videos


class YouTubeSearcher:
    """Thin wrapper around YouTube Data API search for pipeline use."""

    def __init__(self, api_key: str | None = None):
        key = api_key or config.YOUTUBE_API_KEY
        if not key:
            raise ValueError("YOUTUBE_API_KEY is not set. Add it to .env or the environment.")
        self.youtube = build("youtube", "v3", developerKey=key)

    def search(
        self,
        keyword: str,
        max_results: int = 50,
        published_after: str | None = None,
        published_before: str | None = None,
        relevance_language: str | None = None,
    ) -> list[dict]:
        del relevance_language  # reserved for future API filtering
        if published_before is None:
            published_before = to_rfc3339(datetime.now(tz=timezone.utc))
        if published_after is None:
            start = datetime.now(tz=timezone.utc) - timedelta(days=config.SEARCH_PERIOD_DAYS)
            published_after = to_rfc3339(start)
        return search_videos(
            self.youtube,
            keyword,
            published_after,
            published_before,
            max_results,
        )


if __name__ == "__main__":
    run_search()
