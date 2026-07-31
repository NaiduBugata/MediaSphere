"""Critical issue alert template."""

from __future__ import annotations

from typing import Any

from notifications.formatter import format_datetime, truncate
from notifications.utils import location_label, safe_str


def build_text(article: dict[str, Any]) -> str:
    problem = safe_str(article.get("problem")) or truncate(safe_str(article.get("summary")), 300)
    source = safe_str(article.get("source"), "unknown").capitalize()
    severity = safe_str(article.get("severity"), "HIGH").upper()
    return "\n".join(
        [
            "🚨 CRITICAL ISSUE",
            "",
            f"Location: {location_label(article)}",
            "",
            f"Problem: {problem or 'High-priority negative issue detected'}",
            "",
            f"Priority: {severity}",
            "Detected By: AI Engine",
            f"Source: {source}",
            f"Time: {format_datetime(None, fmt='%I:%M %p')}",
            "",
            "Immediate attention recommended.",
            "",
            "MediaSphere Intelligence Platform",
        ]
    )
