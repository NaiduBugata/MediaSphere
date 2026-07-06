"""Data access and aggregation for the daily report.

Fetches categorized articles for a specific day (IST window) from MongoDB
and computes every statistic the report needs. Enrichment (problem flag,
priority, responsible department, recommended action) mirrors the dashboard
logic so email/PDF and dashboard stay consistent.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any

import mongo_store

from . import config
from .logger import get_logger

logger = get_logger("reports.data")

PROBLEM_SENTIMENTS = {"Negative", "Problem"}
HIGH_PRIORITY_CATEGORIES = {"Crime", "Health", "Water", "Transport", "Roads"}

DEPARTMENT_MAP = {
    "Transport": "Roads & Transport (R&B)",
    "Roads": "Roads & Transport (R&B)",
    "Infrastructure": "Infrastructure & Works",
    "Health": "Health & Medical Services",
    "Water": "Rural Water Supply",
    "Employment": "Labour & Employment",
    "Agriculture": "Agriculture & Cooperation",
    "Education": "School Education",
    "Crime": "Police Department",
    "Social Welfare": "Social Welfare Department",
    "Politics": "General Administration",
    "Other": "General Administration",
    "Others": "General Administration",
}

ACTION_MAP = {
    "Transport": "Review road safety measures and coordinate with transport authorities for immediate remediation.",
    "Roads": "Inspect affected road sections and initiate repair or maintenance work.",
    "Infrastructure": "Assess infrastructure damage and escalate to the relevant engineering department.",
    "Health": "Coordinate with district health officials to address the reported health concern.",
    "Water": "Direct the water supply department to investigate and restore services.",
    "Employment": "Engage with the labour department and employer representatives to resolve the dispute.",
    "Agriculture": "Connect farmers with agriculture extension officers for support and guidance.",
    "Education": "Follow up with education department officials regarding the reported issue.",
    "Crime": "Bring to the attention of local police and district administration for prompt action.",
    "Social Welfare": "Coordinate with social welfare officers to ensure beneficiary support.",
    "Politics": "Monitor the situation and engage with local representatives as needed.",
    "Other": "Review the matter and assign to the appropriate department for follow-up.",
    "Others": "Review the matter and assign to the appropriate department for follow-up.",
}

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def previous_day(reference: datetime | None = None) -> date:
    """Return the date to summarize (the day before the reference date)."""
    now = reference or datetime.now(config.REPORT_TIMEZONE)
    if now.tzinfo is None:
        now = now.replace(tzinfo=config.REPORT_TIMEZONE)
    return (now.astimezone(config.REPORT_TIMEZONE) - timedelta(days=1)).date()


def day_window(target: date) -> tuple[datetime, datetime]:
    """Return the [start, end] IST datetimes covering the full target day."""
    start = datetime.combine(target, time.min, tzinfo=config.REPORT_TIMEZONE)
    end = datetime.combine(target, time.max, tzinfo=config.REPORT_TIMEZONE)
    return start, end


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=config.REPORT_TIMEZONE)
    return parsed


def _normalize(doc: dict) -> dict:
    location = doc.get("location") or {}
    if not isinstance(location, dict):
        location = {}
    return {
        "id": str(doc.get("_id", "")),
        "post_id": doc.get("post_id"),
        "title": doc.get("title") or "",
        "summary": doc.get("summary") or "",
        "category": doc.get("category") or "Others",
        "subcategory": doc.get("subcategory") or "",
        "sentiment": doc.get("sentiment") or "",
        "location": {
            "district": location.get("district"),
            "mandal": location.get("mandal"),
            "village": location.get("village"),
            "town": location.get("town"),
            "state": location.get("state") or "Andhra Pradesh",
        },
        "keywords": doc.get("keywords") or [],
        "entities": doc.get("entities") or [],
        "problem": doc.get("problem"),
        "problem_id": doc.get("problem_id"),
        "source_url": doc.get("source_url") or "",
        "source": doc.get("source") or "lokal",
        "channel": doc.get("channel") or "",
        "created_on": doc.get("created_on") or "",
    }


def is_problem(article: dict) -> bool:
    return (article.get("sentiment") or "") in PROBLEM_SENTIMENTS


def derive_priority(article: dict) -> str:
    if not is_problem(article):
        return "Low"
    if (article.get("category") or "") in HIGH_PRIORITY_CATEGORIES:
        return "High"
    return "Medium"


def derive_department(article: dict) -> str:
    category = article.get("category") or "Other"
    return DEPARTMENT_MAP.get(category, DEPARTMENT_MAP["Other"])


def derive_action(article: dict) -> str:
    category = article.get("category") or "Other"
    return ACTION_MAP.get(category, ACTION_MAP["Other"])


def derive_problem_summary(article: dict) -> str:
    if article.get("problem"):
        return str(article["problem"])
    if is_problem(article):
        return article.get("summary") or ""
    return ""


def enrich(article: dict) -> dict:
    enriched = dict(article)
    enriched["is_problem"] = is_problem(article)
    enriched["priority"] = derive_priority(article)
    enriched["department"] = derive_department(article)
    enriched["recommended_action"] = derive_action(article)
    enriched["problem_summary"] = derive_problem_summary(article)
    enriched["created_dt"] = _parse_dt(article.get("created_on") or "")
    return enriched


def format_location(location: dict) -> str:
    if not isinstance(location, dict):
        return "Not specified"
    parts = [location.get("village"), location.get("town"), location.get("mandal"), location.get("district")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else "Not specified"


def format_time(article: dict) -> str:
    dt = article.get("created_dt")
    if not isinstance(dt, datetime):
        return "—"
    return dt.astimezone(config.REPORT_TIMEZONE).strftime("%d %b %Y, %I:%M %p")


def fetch_articles_for_day(target: date) -> list[dict]:
    """Fetch and enrich categorized articles created on the target IST day."""
    collection = mongo_store.get_collection()
    start, end = day_window(target)

    enriched: list[dict] = []
    for doc in collection.find({}):
        article = enrich(_normalize(doc))
        created = article.get("created_dt")
        if not isinstance(created, datetime):
            continue
        created_ist = created.astimezone(config.REPORT_TIMEZONE)
        if start <= created_ist <= end:
            enriched.append(article)

    enriched.sort(key=lambda a: a.get("created_dt") or datetime.min.replace(tzinfo=config.REPORT_TIMEZONE), reverse=True)
    logger.info("Fetched %d articles for %s", len(enriched), target.isoformat())
    return enriched


def _count(items: list[dict], getter) -> dict[str, int]:
    counter: Counter = Counter()
    for item in items:
        key = getter(item)
        if key:
            counter[key] += 1
    return dict(counter)


def _top(counter: dict[str, int], limit: int) -> list[dict]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    ]


def _most(counter: dict[str, int]) -> str:
    if not counter:
        return "None"
    return max(counter.items(), key=lambda kv: kv[1])[0]


def compute_stats(articles: list[dict]) -> dict[str, Any]:
    """Compute every statistic required by the report."""
    total = len(articles)

    sentiment_counts = _count(articles, lambda a: a.get("sentiment") or "Unknown")
    category_counts = _count(articles, lambda a: a.get("category") or "Others")
    district_counts = _count(articles, lambda a: (a.get("location") or {}).get("district"))
    mandal_counts = _count(articles, lambda a: (a.get("location") or {}).get("mandal"))
    village_counts = _count(articles, lambda a: (a.get("location") or {}).get("village"))

    problems = [a for a in articles if a.get("is_problem")]
    high_priority = [a for a in problems if a.get("priority") == "High"]
    positives = [a for a in articles if (a.get("sentiment") or "") == "Positive"]

    keyword_counter: Counter = Counter()
    entity_counter: Counter = Counter()
    for article in articles:
        for kw in article.get("keywords") or []:
            if kw:
                keyword_counter[str(kw)] += 1
        for entity in article.get("entities") or []:
            name = entity.get("name") if isinstance(entity, dict) else str(entity)
            if name:
                entity_counter[name] += 1

    positive = sentiment_counts.get("Positive", 0)
    negative = sentiment_counts.get("Negative", 0)
    statement = sentiment_counts.get("Statement", 0)
    neutral = sentiment_counts.get("Neutral", 0)

    def pct(value: int) -> float:
        return round((value / total) * 100, 1) if total else 0.0

    # Ordered category summary covering every requested category.
    category_summary = []
    for name in config.CATEGORY_ORDER:
        if name == "Others":
            known = set(config.CATEGORY_ORDER) - {"Others"}
            count = sum(v for k, v in category_counts.items() if k not in known)
        else:
            count = category_counts.get(name, 0)
        category_summary.append({"name": name, "count": count})

    def sort_actions(items: list[dict]) -> list[dict]:
        return sorted(
            items,
            key=lambda a: (
                PRIORITY_ORDER.get(a.get("priority"), 3),
                -(a.get("created_dt").timestamp() if isinstance(a.get("created_dt"), datetime) else 0),
            ),
        )

    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "statement": statement,
        "neutral": neutral,
        "problems": len(problems),
        "high_priority_problems": len(high_priority),
        "districts_covered": len([k for k in district_counts if k]),
        "mandals_covered": len([k for k in mandal_counts if k]),
        "villages_covered": len([k for k in village_counts if k]),
        "sentiment_counts": sentiment_counts,
        "category_counts": category_counts,
        "category_summary": category_summary,
        "sentiment_pct": {
            "Positive": pct(positive),
            "Negative": pct(negative),
            "Statement": pct(statement),
            "Neutral": pct(neutral),
        },
        "most_affected_district": _most(district_counts),
        "most_affected_mandal": _most(mandal_counts),
        "most_affected_village": _most(village_counts),
        "top_mandals": _top(mandal_counts, config.TOP_LOCATIONS),
        "top_villages": _top(village_counts, config.TOP_LOCATIONS),
        "top_keywords": [{"name": k, "count": v} for k, v in keyword_counter.most_common(config.MAX_KEYWORDS)],
        "top_entities": [{"name": k, "count": v} for k, v in entity_counter.most_common(config.MAX_ENTITIES)],
        "action_items": sort_actions(problems)[: config.MAX_ACTION_ITEMS],
        "positive_items": positives[: config.MAX_POSITIVE_ITEMS],
        "most_common_category": _most(category_counts),
    }
