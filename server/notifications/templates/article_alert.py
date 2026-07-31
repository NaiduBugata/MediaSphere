"""New-article alert templates (email subject/HTML delegated elsewhere)."""

from __future__ import annotations

from typing import Any

from notifications.formatter import format_datetime, truncate
from notifications.utils import location_label, safe_str


def build_text(article: dict[str, Any]) -> str:
    title = safe_str(article.get("title"), "Untitled")
    summary = truncate(safe_str(article.get("summary")), 400)
    source = safe_str(article.get("source"), "unknown").capitalize()
    category = safe_str(article.get("category"), "News")
    sentiment = safe_str(article.get("sentiment"), "Neutral")
    published = format_datetime(article.get("created_on"), fmt="%d %b %Y")
    url = safe_str(article.get("source_url") or article.get("url"), "")
    loc = location_label(article)

    lines = [
        "📰 NEW NEWS DETECTED",
        "",
        f"Source: {source}",
        f"Location: {loc}",
        f"Category: {category}",
        f"Sentiment: {sentiment}",
        "",
        f"Headline: {title}",
        "",
        f"Summary: {summary or 'N/A'}",
        "",
        f"Published: {published}",
    ]
    if url:
        lines.extend(["", f"Read More: {url}"])
    lines.extend(["", "MediaSphere Intelligence Platform"])
    return "\n".join(lines)
