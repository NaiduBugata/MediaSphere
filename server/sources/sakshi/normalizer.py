"""Map raw Sakshi extraction into the MediaSphere article shape."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sources.sakshi.parser import _stable_article_id


def normalize_sakshi_article(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one raw extracted article (with constituency validation info)."""
    url = (raw.get("url") or "").strip()
    title = (raw.get("title") or "").strip()
    content = (raw.get("content") or "").strip()
    published = raw.get("published_at") or datetime.now(timezone.utc).isoformat()
    article_id = _stable_article_id(url)
    validation = raw.get("_constituency_validation") or {}

    return {
        "id": article_id,
        "source": "sakshi",
        "source_type": "newspaper",
        "title": title,
        "content": content,
        "article": content,
        "summary": raw.get("summary") or "",
        "published_at": published,
        "created_on": published,
        "author": raw.get("author") or "",
        "category": raw.get("category") or "",
        "subcategory": "",
        "tags": raw.get("tags") or [],
        "keywords": [],
        "entities": [],
        "location": {},
        "thumbnail": raw.get("thumbnail") or "",
        "description": raw.get("description") or "",
        "source_url": url,
        "url": url,
        "language": "te",
        "channel": "Sakshi",
        "constituency_score": validation.get("score"),
        "constituency_match_reason": validation.get("reason"),
    }
