"""Map cleaned YouTube transcripts into the collector article shape."""

from __future__ import annotations

from typing import Any


def normalize_video(item: dict[str, Any], clean_text: str) -> dict[str, Any]:
    """Build the collector article dict for one transcript item."""
    video_id = item["video_id"]
    return {
        "id": video_id,
        "video_id": video_id,
        "title": item.get("title", ""),
        "content": clean_text,
        "channel": item.get("channel", ""),
        "url": item.get("url", ""),
        "created_on": item.get("published_at", ""),
    }
