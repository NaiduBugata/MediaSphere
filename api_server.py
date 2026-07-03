"""Flask API server for MediaSphere constituency news dashboard."""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

import mongo_store

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("api_server")

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]

app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)


def _normalize_article(doc: dict) -> dict:
    """Normalize a MongoDB document for JSON serialization."""
    location = doc.get("location") or {}
    if not isinstance(location, dict):
        location = {}

    normalized = {
        "_id": str(doc.get("_id", "")),
        "post_id": doc.get("post_id"),
        "title": doc.get("title") or "",
        "summary": doc.get("summary") or "",
        "category": doc.get("category") or "",
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
        "created_on": doc.get("created_on") or "",
        "first_seen_at": doc.get("first_seen_at") or "",
        "last_updated_at": doc.get("last_updated_at") or "",
    }
    return normalized


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _date_key(value: str) -> str | None:
    parsed = _parse_date(value)
    if not parsed:
        return None
    return parsed.date().isoformat()


def _compute_stats(articles: list[dict]) -> dict:
    total = len(articles)
    sentiment_counts = Counter(a.get("sentiment") or "Unknown" for a in articles)
    category_counts = Counter(a.get("category") or "Other" for a in articles)
    district_counts = Counter((a.get("location") or {}).get("district") or "Unknown" for a in articles)
    mandal_counts = Counter((a.get("location") or {}).get("mandal") or "Unknown" for a in articles)
    village_counts = Counter((a.get("location") or {}).get("village") or "Unknown" for a in articles)

    keyword_counter: Counter = Counter()
    entity_counter: Counter = Counter()
    for article in articles:
        for kw in article.get("keywords") or []:
            if kw:
                keyword_counter[kw] += 1
        for entity in article.get("entities") or []:
            name = entity.get("name") if isinstance(entity, dict) else str(entity)
            if name:
                entity_counter[name] += 1

    today = datetime.now(timezone.utc).date()
    daily_counts: dict[str, int] = defaultdict(int)
    for i in range(7):
        day = (today - timedelta(days=i)).isoformat()
        daily_counts[day] = 0

    for article in articles:
        key = _date_key(article.get("created_on") or "")
        if key and key in daily_counts:
            daily_counts[key] += 1

    daily_trend = [{"date": day, "count": daily_counts[day]} for day in sorted(daily_counts.keys())]

    problem_count = sum(
        1 for a in articles if (a.get("sentiment") or "") in ("Negative", "Problem")
    )

    return {
        "total": total,
        "sentiment": dict(sentiment_counts),
        "category": dict(category_counts),
        "district": dict(district_counts),
        "mandal": dict(mandal_counts),
        "village": dict(village_counts),
        "daily_trend": daily_trend,
        "top_keywords": [{"name": k, "count": v} for k, v in keyword_counter.most_common(20)],
        "top_entities": [{"name": k, "count": v} for k, v in entity_counter.most_common(20)],
        "positive_count": sentiment_counts.get("Positive", 0),
        "negative_count": sentiment_counts.get("Negative", 0),
        "neutral_count": sentiment_counts.get("Neutral", 0),
        "statement_count": sentiment_counts.get("Statement", 0),
        "problem_count": problem_count,
    }


@app.route("/api/news", methods=["GET"])
def get_news():
    """Return all categorized articles, newest first."""
    try:
        collection = mongo_store.get_collection()
        cursor = collection.find({}).sort("created_on", -1)
        articles = [_normalize_article(doc) for doc in cursor]
        return jsonify({"articles": articles, "count": len(articles)})
    except Exception as exc:
        logger.exception("Failed to fetch news: %s", exc)
        return jsonify({"error": str(exc), "articles": [], "count": 0}), 500


@app.route("/api/news/stats", methods=["GET"])
def get_news_stats():
    """Return aggregated statistics for all articles."""
    try:
        collection = mongo_store.get_collection()
        cursor = collection.find({})
        articles = [_normalize_article(doc) for doc in cursor]
        stats = _compute_stats(articles)
        stats["generated_at"] = datetime.now(timezone.utc).isoformat()
        return jsonify(stats)
    except Exception as exc:
        logger.exception("Failed to fetch stats: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "5000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    logger.info("Starting MediaSphere API on http://%s:%s (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug)
