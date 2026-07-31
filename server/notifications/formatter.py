"""Format AI / pipeline data into professional notification text."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from notifications import config
from notifications.utils import location_label, safe_str

WHATSAPP_MAX_CHARS = 3500  # leave margin under Meta's ~4096 limit


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.NOTIFICATION_TIMEZONE)
    except Exception:  # noqa: BLE001
        return ZoneInfo("Asia/Kolkata")


def format_datetime(value: Any, *, fmt: str = "%d %b %Y %I:%M %p") -> str:
    """Format a datetime or ISO string in the notification timezone."""
    if value is None or value == "":
        return datetime.now(_tz()).strftime(fmt)
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text[:40]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(_tz()).strftime(fmt)


def truncate(text: str, max_chars: int = WHATSAPP_MAX_CHARS) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def wrap_url(url: str) -> str:
    return safe_str(url)


def article_template_variables(article: dict[str, Any]) -> list[str]:
    """Ordered body variables for the article-alert WhatsApp template."""
    summary = truncate(safe_str(article.get("summary") or article.get("problem")), 200)
    headline = truncate(safe_str(article.get("title"), "Untitled"), 120)
    return [
        safe_str(article.get("source"), "unknown").capitalize(),
        safe_str(article.get("category"), "News"),
        safe_str(article.get("sentiment"), "Neutral"),
        headline,
        summary or "See article for details.",
        format_datetime(article.get("created_on") or article.get("created_dt"), fmt="%d %b %Y"),
        wrap_url(safe_str(article.get("source_url") or article.get("url"), "N/A")),
    ]


def critical_template_variables(article: dict[str, Any]) -> list[str]:
    problem = safe_str(article.get("problem"))
    if not problem:
        problem = truncate(safe_str(article.get("summary")), 200) or "Critical issue detected"
    return [
        location_label(article),
        truncate(problem, 200),
        safe_str(article.get("severity"), "HIGH").upper(),
        safe_str(article.get("source"), "unknown").capitalize(),
        format_datetime(None, fmt="%I:%M %p"),
    ]
