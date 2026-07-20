"""Typed shapes for Lokal collector output."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class LokalArticle(TypedDict):
    """Normalized article as saved in the collector JSON envelope."""

    id: Any
    title: str
    content: str
    created_on: str
    url: str
    raw: Dict[str, Any]


class CollectorEnvelope(TypedDict):
    """Top-level structure of the saved collector JSON file."""

    generated_at: str
    collector: str
    source: str
    tag_id: int
    lookback_hours: int
    total_articles: int
    articles: List[LokalArticle]
