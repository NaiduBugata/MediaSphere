"""Fetch Telugu YouTube captions."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from tqdm import tqdm
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

from . import config

logger = logging.getLogger("youtube.transcripts")

PERMANENT_ERRORS = (NoTranscriptFound, TranscriptsDisabled)
_api = YouTubeTranscriptApi()
_lock = Lock()


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, PERMANENT_ERRORS):
        return False
    msg = str(exc).lower()
    return any(code in msg for code in ("429", "503", "timeout", "connection"))


def fetch_transcript(video: dict) -> dict | None:
    video_id = video["video_id"]
    last_exc = None

    for attempt in range(1, 4):
        try:
            transcript = _api.fetch(video_id, languages=config.TRANSCRIPT_LANGUAGES)
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
            logger.debug("No Telugu transcript | %s | %s", video["title"][:50], exc)
            return None
        except Exception as exc:
            last_exc = exc
            if _is_transient(exc) and attempt < 3:
                time.sleep(2)
            else:
                break

    logger.warning("Transcript failed | %s | %s", video["title"][:50], last_exc)
    return None


def _load_existing() -> list[dict]:
    if not config.TRANSCRIPTS_JSON.exists():
        return []
    try:
        data = json.loads(config.TRANSCRIPTS_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def run_collect() -> list[dict]:
    """Fetch transcripts for videos not yet cached locally."""
    if not config.VIDEOS_JSON.exists():
        raise FileNotFoundError(f"Missing {config.VIDEOS_JSON}; run search first")

    videos = json.loads(config.VIDEOS_JSON.read_text(encoding="utf-8"))
    if not videos:
        return []

    existing = _load_existing()
    seen_ids = {r["video_id"] for r in existing}
    to_fetch = [v for v in videos if v["video_id"] not in seen_ids]

    logger.info(
        "Transcripts | videos: %d | cached: %d | to fetch: %d",
        len(videos),
        len(seen_ids),
        len(to_fetch),
    )

    if not to_fetch:
        return existing

    new_transcripts: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_transcript, v): v for v in to_fetch}
        with tqdm(total=len(to_fetch), desc="YouTube transcripts", unit="video") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result:
                    with _lock:
                        new_transcripts.append(result)
                pbar.update(1)

    all_transcripts = existing + new_transcripts
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.TRANSCRIPTS_JSON, "w", encoding="utf-8") as f:
        json.dump(all_transcripts, f, ensure_ascii=False, indent=2)

    logger.info("Transcripts saved: %d total (%d new)", len(all_transcripts), len(new_transcripts))
    return all_transcripts
