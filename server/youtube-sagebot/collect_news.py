"""
collect_news.py — Stage 2: Transcript Collection
Enhanced with concurrent fetching, retry logic, deduplication, and progress bars.
"""

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from tqdm import tqdm
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

import config

# ── Logging setup ──────────────────────────────────────────────────────────────
os.makedirs(config.DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [collect] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.PIPELINE_LOG, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)
PERMANENT_ERRORS = (NoTranscriptFound, TranscriptsDisabled)

api = YouTubeTranscriptApi()
results_lock = Lock()


def is_transient(exc: Exception) -> bool:
    """Return True if the exception looks transient (worth retrying)."""
    if isinstance(exc, PERMANENT_ERRORS):
        return False
    msg = str(exc).lower()
    return any(code in msg for code in ("429", "503", "timeout", "connection"))


def fetch_transcript(video: dict) -> dict | None:
    """Fetch Telugu transcript for a single video with retry logic."""
    video_id = video["video_id"]
    last_exc = None

    for attempt in range(1, 4):  # 3 attempts
        try:
            transcript = api.fetch(video_id, languages=config.TRANSCRIPT_LANGUAGES)
            text = " ".join(item.text for item in transcript)
            return {
                "video_id": video_id,
                "title": video["title"],
                "channel": video["channel"],
                "published_at": video["published_at"],
                "url": video["url"],
                "transcript": text,
            }
        except PERMANENT_ERRORS as exc:
            logger.warning("SKIP (no Telugu transcript) | %s | %s", video["title"][:60], exc)
            return None
        except Exception as exc:
            last_exc = exc
            if is_transient(exc) and attempt < 3:
                logger.warning("Transient error (attempt %d/3) for '%s': %s — retrying in 2s",
                               attempt, video["title"][:60], exc)
                time.sleep(2)
            else:
                break

    logger.error("FAILED after 3 retries | %s | %s", video["title"][:60], last_exc)
    return None


def load_json_safe(path: str) -> list:
    """Load JSON array from file, return empty list if file missing/corrupt."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def run_collect(skip_cache: bool = False) -> list[dict]:
    """Main collection function. Returns list of transcript records."""
    # Load videos
    if not os.path.exists(config.VIDEOS_JSON):
        logger.error("videos.json not found at '%s'. Run Stage 1 first.", config.VIDEOS_JSON)
        sys.exit(1)

    try:
        with open(config.VIDEOS_JSON, "r", encoding="utf-8") as f:
            videos = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Cannot read videos.json: %s", exc)
        sys.exit(1)

    if not videos:
        logger.warning("videos.json is empty — nothing to collect.")
        return []

    # Load existing transcripts for deduplication
    existing: list[dict] = [] if skip_cache else load_json_safe(config.TRANSCRIPTS_JSON)
    seen_ids: set[str] = {r["video_id"] for r in existing}

    to_fetch = [v for v in videos if v["video_id"] not in seen_ids]
    logger.info("Videos total: %d | Already cached: %d | To fetch: %d",
                len(videos), len(seen_ids), len(to_fetch))

    if not to_fetch:
        logger.info("All transcripts already collected. Use --skip-cache to re-fetch.")
        return existing

    new_transcripts: list[dict] = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_transcript, v): v for v in to_fetch}
        with tqdm(total=len(to_fetch), desc="Collecting transcripts", unit="video") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result:
                    with results_lock:
                        new_transcripts.append(result)
                pbar.update(1)

    all_transcripts = existing + new_transcripts

    # Save merged results
    with open(config.TRANSCRIPTS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_transcripts, f, ensure_ascii=False, indent=2)

    logger.info("Stage 2 complete: %d transcripts saved (%d new) to %s",
                len(all_transcripts), len(new_transcripts), config.TRANSCRIPTS_JSON)
    return all_transcripts


class TranscriptCollector:
    """Fetch YouTube captions for pipeline use."""

    def __init__(self):
        self.api = YouTubeTranscriptApi()

    def get_transcript(self, video_id: str, languages: list[str] | None = None) -> str | None:
        langs = languages or config.TRANSCRIPT_LANGUAGES
        try:
            transcript = self.api.fetch(video_id, languages=langs)
            return " ".join(item.text for item in transcript)
        except PERMANENT_ERRORS:
            return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Telugu News Pipeline — Stage 2: Transcript Collection")
    parser.add_argument("--skip-cache", action="store_true", help="Re-fetch all transcripts")
    args = parser.parse_args()
    run_collect(skip_cache=args.skip_cache)
