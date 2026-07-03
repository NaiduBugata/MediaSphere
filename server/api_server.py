"""Flask API server for MediaSphere constituency news dashboard."""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

import mongo_store
from reports import config as report_config
from reports import db_service as report_db
from reports import report_generator, scheduler

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


@app.route("/api/reports/history", methods=["GET"])
def reports_history():
    """Return the daily report delivery history (newest first)."""
    try:
        limit = int(request.args.get("limit", "60"))
        return jsonify({"reports": report_db.history(limit=limit)})
    except Exception as exc:
        logger.exception("Failed to fetch report history: %s", exc)
        return jsonify({"error": str(exc), "reports": []}), 500


@app.route("/api/reports/<report_id>", methods=["GET"])
def reports_detail(report_id: str):
    """Return a single report record by _id or report_date."""
    try:
        doc = report_db.get_by_id(report_id)
        if not doc:
            return jsonify({"error": "Report not found"}), 404
        return jsonify(doc)
    except Exception as exc:
        logger.exception("Failed to fetch report %s: %s", report_id, exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reports/send-now", methods=["POST"])
def reports_send_now():
    """Generate and send the report (dedup applies unless force=true)."""
    payload = request.get_json(silent=True) or {}
    target = _parse_report_date(payload.get("date"))
    force = bool(payload.get("force", False))
    try:
        result = report_generator.generate_and_send(target, force=force)
        status_code = 200 if result.get("status") in ("sent", "skipped") else 502
        return jsonify(result), status_code
    except Exception as exc:
        logger.exception("send-now failed: %s", exc)
        return jsonify({"status": "error", "error": str(exc)}), 500


@app.route("/api/reports/regenerate", methods=["POST"])
def reports_regenerate():
    """Force regeneration and resend of a report for a given date."""
    payload = request.get_json(silent=True) or {}
    target = _parse_report_date(payload.get("date"))
    try:
        result = report_generator.generate_and_send(target, force=True)
        status_code = 200 if result.get("status") == "sent" else 502
        return jsonify(result), status_code
    except Exception as exc:
        logger.exception("regenerate failed: %s", exc)
        return jsonify({"status": "error", "error": str(exc)}), 500


def _parse_report_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _start_scheduler() -> None:
    """Start the daily report scheduler unless running under the reloader parent."""
    if os.getenv("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        try:
            scheduler.start()
        except Exception as exc:
            logger.exception("Failed to start report scheduler: %s", exc)


if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "5000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    app.debug = debug
    logger.info("Starting MediaSphere API on http://%s:%s (debug=%s)", host, port, debug)
    _start_scheduler()
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
