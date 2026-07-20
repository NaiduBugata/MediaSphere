"""Parsing helpers for Lokal API payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def parse_post_date(value: Any) -> Optional[datetime]:
    """
    Parse a post timestamp from common ISO-8601 formats.

    Purpose:
        Normalize API timestamps for reliable cutoff comparisons.

    Parameters:
        value: Raw created_on value from the API.

    Returns:
        Timezone-aware datetime on success, otherwise None.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)

    return parsed.astimezone(timezone.utc)
