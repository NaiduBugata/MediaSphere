"""Normalization and deduplication of Lokal API posts."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sources.lokal.constants import WEBSITE_BASE_URL
from sources.lokal.parser import parse_post_date

logger = logging.getLogger("lokal_collector")


def build_article_url(post: Dict[str, Any]) -> str:
    """
    Build a best-effort public URL for a post.

    Purpose:
        Provide a usable link even when the API does not expose the full
        canonical path segments.

    Parameters:
        post: Raw post object from the API.

    Returns:
        Best-effort article URL string.
    """
    custom_link = post.get("custom_link")
    if custom_link:
        return str(custom_link)

    slug = str(post.get("slug") or "").strip()
    post_id = post.get("id")
    if slug and post_id is not None:
        return f"{WEBSITE_BASE_URL}/{slug}-{post_id}"

    if post_id is not None:
        return f"{WEBSITE_BASE_URL}/post/{post_id}"

    return ""


def normalize_article(post: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize one API post into the collector output schema.

    Purpose:
        Map API fields to the saved article structure while preserving the
        complete original payload in raw.

    Parameters:
        post: Raw post dictionary from the API results list.

    Returns:
        Normalized article dictionary, or None when required fields are missing.
    """
    if not isinstance(post, dict):
        logger.warning("Skipped post with unexpected type: %s", type(post).__name__)
        return None

    post_id = post.get("id")
    if post_id is None:
        logger.warning("Skipped post without id")
        return None

    created_on = post.get("created_on")
    if created_on is None:
        logger.warning("Skipped post id=%s without created_on", post_id)
        return None

    return {
        "id": post_id,
        "title": post.get("title") or "",
        "content": post.get("content") or "",
        "created_on": str(created_on),
        "url": build_article_url(post),
        "raw": post,
    }


def remove_duplicates(articles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove duplicate articles by id, keeping the newest created_on value.

    Purpose:
        Ensure pagination overlap does not produce duplicate saved records.

    Parameters:
        articles: List of normalized article dictionaries.

    Returns:
        Tuple of (deduplicated articles, duplicates removed count).
    """
    newest_by_id: Dict[Any, Dict[str, Any]] = {}

    for article in articles:
        article_id = article.get("id")
        if article_id is None:
            continue

        existing = newest_by_id.get(article_id)
        if existing is None:
            newest_by_id[article_id] = article
            continue

        existing_dt = parse_post_date(existing.get("created_on"))
        current_dt = parse_post_date(article.get("created_on"))

        if current_dt is not None and (existing_dt is None or current_dt >= existing_dt):
            newest_by_id[article_id] = article

    deduplicated = list(newest_by_id.values())
    duplicates_removed = len(articles) - len(deduplicated)
    return deduplicated, duplicates_removed
