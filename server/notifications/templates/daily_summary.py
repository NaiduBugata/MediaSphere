"""Daily constituency summary template."""

from __future__ import annotations

from typing import Any

from notifications import config
from notifications.utils import safe_str


def build_text(stats: dict[str, Any], *, report_date: str) -> str:
    total = stats.get("total") or stats.get("article_count") or 0
    positive = stats.get("positive_count") or (stats.get("sentiment") or {}).get("Positive", 0)
    negative = stats.get("negative_count") or (stats.get("sentiment") or {}).get("Negative", 0)
    neutral = stats.get("neutral_count") or (stats.get("sentiment") or {}).get("Neutral", 0)
    problems = stats.get("problem_count") or stats.get("problems") or stats.get("high_priority_problems") or 0

    categories = stats.get("top_categories") or stats.get("category") or {}
    if isinstance(categories, dict):
        top_cat = ", ".join(f"{k} ({v})" for k, v in list(categories.items())[:5]) or "N/A"
    else:
        top_cat = safe_str(categories, "N/A")

    locations = stats.get("top_locations") or stats.get("district") or {}
    if isinstance(locations, dict):
        top_loc = ", ".join(f"{k} ({v})" for k, v in list(locations.items())[:5]) or "N/A"
    else:
        top_loc = safe_str(locations, "N/A")

    dashboard = config.DASHBOARD_URL or "N/A"

    return "\n".join(
        [
            "📊 DAILY NEWS SUMMARY",
            "",
            f"Date: {report_date}",
            f"Articles: {total}",
            f"Positive: {positive}",
            f"Negative: {negative}",
            f"Neutral: {neutral}",
            "",
            f"Top Categories: {top_cat}",
            f"Top Locations: {top_loc}",
            f"Critical Issues: {problems}",
            "",
            f"Dashboard: {dashboard}",
            "",
            "Generated automatically by MediaSphere.",
        ]
    )
