"""AI-powered executive summary generation using Groq.

Produces a 150-250 word narrative summary of the day's constituency news.
Falls back to a deterministic, stats-based summary if Groq is unavailable,
so the report is never blocked by the AI layer.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from . import config
from .data_service import format_location
from .logger import get_logger

logger = get_logger("reports.ai")

_SYSTEM_PROMPT = (
    "You are a senior political intelligence analyst preparing a concise executive "
    "briefing for a Member of Parliament. Write in clear, professional English. "
    "Produce a single cohesive summary of 150-250 words (no bullet lists, no headings). "
    "Cover: the overall constituency situation, major positive developments, major "
    "concerns/problems, departments that require attention, and the general public "
    "sentiment. Be factual and grounded strictly in the data provided. Do not invent "
    "specifics that are not present."
)


def _build_context(target: date, articles: list[dict], stats: dict[str, Any]) -> str:
    lines = [
        f"Constituency: {config.CONSTITUENCY_NAME}",
        f"Report date: {target.strftime('%d %B %Y')}",
        f"Total articles: {stats['total']}",
        f"Positive: {stats['positive']}, Negative: {stats['negative']}, "
        f"Statement: {stats['statement']}, Neutral: {stats['neutral']}",
        f"Problems identified: {stats['problems']} (high priority: {stats['high_priority_problems']})",
        f"Most common category: {stats['most_common_category']}",
        f"Most affected mandal: {stats['most_affected_mandal']}, "
        f"village: {stats['most_affected_village']}",
    ]

    category_bits = [f"{c['name']}: {c['count']}" for c in stats["category_summary"] if c["count"]]
    if category_bits:
        lines.append("Category breakdown: " + ", ".join(category_bits))

    if stats["action_items"]:
        lines.append("Top problems requiring attention:")
        for item in stats["action_items"][:6]:
            lines.append(
                f"- [{item['priority']}] {item['title']} "
                f"({item['category']}, {format_location(item['location'])}) "
                f"-> {item['department']}"
            )

    if stats["positive_items"]:
        lines.append("Positive developments:")
        for item in stats["positive_items"][:5]:
            lines.append(f"- {item['title']} ({item['category']}, {format_location(item['location'])})")

    return "\n".join(lines)


def _template_summary(target: date, stats: dict[str, Any]) -> str:
    """Deterministic fallback summary assembled from computed statistics."""
    if stats["total"] == 0:
        return (
            f"No categorized news was recorded for {config.CONSTITUENCY_NAME} constituency on "
            f"{target.strftime('%d %B %Y')}. There are no developments, problems, or announcements "
            "to report for this period. Monitoring continues and the next report will capture any "
            "newly published news."
        )

    sentiment = "balanced"
    if stats["negative"] > stats["positive"]:
        sentiment = "predominantly negative, reflecting public concerns"
    elif stats["positive"] > stats["negative"]:
        sentiment = "largely positive"

    parts = [
        f"On {target.strftime('%d %B %Y')}, {stats['total']} categorized news items were recorded "
        f"across {config.CONSTITUENCY_NAME} constituency. Overall public sentiment was {sentiment}, "
        f"with {stats['positive']} positive, {stats['negative']} negative, and {stats['statement']} "
        f"statement-type reports.",
    ]

    if stats["problems"]:
        dept_focus = stats["action_items"][0]["department"] if stats["action_items"] else "relevant departments"
        parts.append(
            f"{stats['problems']} issues require attention ({stats['high_priority_problems']} high priority), "
            f"concentrated in {stats['most_affected_mandal']} mandal. The {dept_focus} and related "
            f"departments should prioritise these grievances."
        )
    else:
        parts.append("No actionable problems were flagged during this period.")

    if stats["positive_items"]:
        top_positive = stats["positive_items"][0]["title"]
        parts.append(f"Notable positive developments include: {top_positive}.")

    parts.append(
        f"The most active category was {stats['most_common_category']}. Most reported locations were "
        f"{stats['most_affected_mandal']} (mandal) and {stats['most_affected_village']} (village)."
    )

    return " ".join(parts)


def generate_executive_summary(target: date, articles: list[dict], stats: dict[str, Any]) -> str:
    """Generate the executive summary, preferring Groq with a safe fallback."""
    keys = config.groq_api_keys()
    if not keys:
        logger.warning("No Groq API keys configured; using template summary.")
        return _template_summary(target, stats)

    context = _build_context(target, articles, stats)

    try:
        from groq import Groq

        client = Groq(api_key=keys[0], timeout=config.GROQ_TIMEOUT_SECONDS)
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            temperature=0.3,
            max_tokens=500,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Constituency data for the day:\n\n{context}"},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        if text:
            logger.info("Groq executive summary generated (%d chars).", len(text))
            return text
        logger.warning("Groq returned empty summary; using template fallback.")
    except Exception as exc:  # noqa: BLE001 - never let AI failures break the report
        logger.warning("Groq summary failed (%s); using template fallback.", exc)

    return _template_summary(target, stats)
