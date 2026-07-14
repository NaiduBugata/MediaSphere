"""Flask API server for MediaSphere constituency news dashboard."""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

import mongo_store
from reports import config as report_config
from reports import db_service as report_db
from reports import report_generator, scheduler
from whatsapp.routes import whatsapp_bp

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("api_server")

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]

app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)
app.register_blueprint(whatsapp_bp)


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
        "source": doc.get("source") or "lokal",
        "channel": doc.get("channel") or "",
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


def _article_sort_timestamp(article: dict) -> float:
    """Newest-first ordering across Lokal and YouTube (mixed date formats)."""
    for field in ("created_on", "first_seen_at", "last_updated_at"):
        parsed = _parse_date(article.get(field) or "")
        if parsed:
            return parsed.timestamp()
    return 0.0


def _sort_articles_newest_first(articles: list[dict]) -> list[dict]:
    return sorted(articles, key=_article_sort_timestamp, reverse=True)


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

    source_counts = Counter(a.get("source") or "lokal" for a in articles)

    return {
        "total": total,
        "by_source": dict(source_counts),
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
    """Return categorized articles, newest first. Optional ?source=lokal|youtube|all."""
    try:
        source_filter = (request.args.get("source") or "all").lower()

        collection = mongo_store.get_collection()
        # Do not use MongoDB .sort("created_on") — Lokal and YouTube store mixed
        # ISO string formats (+05:30 with microseconds vs Z), so lexicographic sort
        # misorders across sources. Parse and sort in Python instead.
        cursor = collection.find({})
        articles = [_normalize_article(doc) for doc in cursor]
        articles = _sort_articles_newest_first(articles)

        if source_filter == "lokal":
            articles = [a for a in articles if a.get("source", "lokal") == "lokal"]
        elif source_filter == "youtube":
            articles = [a for a in articles if a.get("source") == "youtube"]

        data_revision = None
        try:
            import pipeline_state

            data_revision = pipeline_state.get_data_revision()
        except Exception:  # noqa: BLE001 - news must not fail if state unavailable
            data_revision = None

        response = jsonify(
            {
                "articles": articles,
                "count": len(articles),
                "data_revision": data_revision,
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        logger.exception("Failed to fetch news: %s", exc)
        response = jsonify({"error": "Failed to fetch news", "articles": [], "count": 0})
        response.headers["Cache-Control"] = "no-store"
        return response, 500


@app.route("/api/news/stats", methods=["GET"])
def get_news_stats():
    """Return aggregated statistics for all articles."""
    try:
        collection = mongo_store.get_collection()
        cursor = collection.find({})
        articles = [_normalize_article(doc) for doc in cursor]
        stats = _compute_stats(articles)
        stats["generated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            import pipeline_state

            stats["data_revision"] = pipeline_state.get_data_revision()
        except Exception:  # noqa: BLE001
            stats["data_revision"] = None
        response = jsonify(stats)
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        logger.exception("Failed to fetch stats: %s", exc)
        response = jsonify({"error": "Failed to fetch stats"})
        response.headers["Cache-Control"] = "no-store"
        return response, 500


@app.route("/api/health", methods=["GET"])
def health():
    """Shallow liveness probe with optional Mongo reachability (no secrets)."""
    mongo_ok = False
    try:
        mongo_store.get_client().admin.command("ping")
        mongo_ok = True
    except Exception:  # noqa: BLE001
        mongo_ok = False
    return jsonify({"status": "ok", "mongo": mongo_ok})


@app.route("/api/pipeline/health", methods=["GET"])
def pipeline_health():
    """Pipeline scheduler diagnostics (sanitized; no secrets/stack traces)."""
    try:
        import pipeline_scheduler

        snapshot = pipeline_scheduler.health_snapshot()
        raw_status = snapshot.get("status")
        if raw_status == "failed":
            snapshot["status"] = "unhealthy"
        elif snapshot.get("scheduler") == "running":
            snapshot["status"] = "healthy"
        return jsonify(snapshot)
    except Exception as exc:
        logger.exception("pipeline health failed: %s", exc)
        return jsonify({"scheduler": "unknown", "status": "unhealthy", "error": "unavailable"}), 500


@app.route("/api/database/health", methods=["GET"])
def database_health():
    """MongoDB connectivity diagnostics without exposing URIs or credentials."""
    try:
        import pipeline_state

        ping = pipeline_state.ping_mongo()
        return jsonify(
            {
                "status": "healthy",
                "ok": True,
                "latency_ms": ping.get("latency_ms"),
                "database": ping.get("database"),
                "articles_collection": ping.get("articles_collection"),
                "articles_count": ping.get("articles_count"),
            }
        )
    except Exception as exc:
        logger.exception("database health failed: %s", exc)
        return jsonify({"status": "unhealthy", "ok": False, "error": "unavailable"}), 500


@app.route("/api/pipeline/run-now", methods=["POST"])
def pipeline_run_now():
    """Admin-only manual trigger. Requires X-Pipeline-Admin-Token when configured."""
    import pipeline_config
    import pipeline_scheduler

    expected = pipeline_config.PIPELINE_ADMIN_TOKEN
    if not expected:
        return jsonify({"status": "disabled", "error": "PIPELINE_ADMIN_TOKEN is not configured"}), 503

    provided = request.headers.get("X-Pipeline-Admin-Token", "")
    if provided != expected:
        return jsonify({"status": "forbidden", "error": "Invalid admin token"}), 403

    if not pipeline_scheduler.is_running() and not _truthy("PIPELINE_ON_API"):
        return jsonify({"status": "error", "error": "Pipeline scheduler is not enabled"}), 503

    pipeline_scheduler.run_now()
    return jsonify({"status": "accepted", "message": "Pipeline cycle triggered"}), 202


@app.route("/api/reports/history", methods=["GET"])
def reports_history():
    """Return the daily report delivery history (newest first)."""
    try:
        limit = int(request.args.get("limit", "60"))
        return jsonify({"reports": report_db.history(limit=limit)})
    except Exception as exc:
        logger.exception("Failed to fetch report history: %s", exc)
        return jsonify({"error": "Failed to fetch report history", "reports": []}), 500


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


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _start_scheduler() -> None:
    """Start report + pipeline schedulers unless running under the reloader parent."""
    # Under Werkzeug's debug reloader, only the child (WERKZEUG_RUN_MAIN=true)
    # should own the schedulers so jobs are not registered twice.
    if app.debug and os.getenv("WERKZEUG_RUN_MAIN") != "true":
        return

    if _truthy("REPORT_SCHEDULER_ON_API"):
        try:
            scheduler.start(run_catch_up=_truthy("REPORT_CATCHUP_ON_START"))
        except Exception as exc:
            logger.exception("Failed to start report scheduler: %s", exc)
    else:
        logger.info("Report scheduler not started on API (REPORT_SCHEDULER_ON_API=false).")

    if _truthy("PIPELINE_ON_API"):
        try:
            import pipeline_scheduler

            pipeline_scheduler.start(run_catch_up=_truthy("PIPELINE_CATCHUP_ON_START", "true"))
        except Exception as exc:
            logger.exception("Failed to start pipeline scheduler: %s", exc)
    else:
        logger.info("Pipeline scheduler not started on API (PIPELINE_ON_API=false).")


if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "5000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    app.debug = debug
    logger.info("Starting MediaSphere API on http://%s:%s (debug=%s)", host, port, debug)
    _start_scheduler()
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
