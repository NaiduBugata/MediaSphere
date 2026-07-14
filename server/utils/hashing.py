"""Content fingerprinting utilities for deduplication."""

from __future__ import annotations

import hashlib
import re


def normalize_title(title: str) -> str:
    """Normalize a title for comparison: lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", title.lower().strip())


def content_fingerprint(
    source: str,
    title: str,
    *,
    body: str | None = None,
    published_at: str | None = None,
    source_url: str | None = None,
) -> str:
    """SHA-256 fingerprint over title + body + published_at + source."""
    normalized = normalize_title(title)
    text = re.sub(r"\s+", " ", (body or "").strip())
    published = (published_at or "").strip()
    raw = f"{normalized}|{text}|{published}|{source}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
