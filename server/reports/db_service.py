"""Persistence for daily report history and de-duplication.

Uses a `daily_reports` collection in the same MediaSphere database. The
report_date (the summarized day, YYYY-MM-DD) is the unique key that prevents
duplicate reports/emails for the same day.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pymongo.collection import Collection

import mongo_store

from .logger import get_logger

logger = get_logger("reports.db")

COLLECTION_NAME = "daily_reports"

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"


def get_collection() -> Collection:
    """Return the daily_reports collection, ensuring a unique report_date index."""
    client = mongo_store.get_client()
    collection = client[mongo_store.MONGODB_DB_NAME][COLLECTION_NAME]
    collection.create_index("report_date", unique=True)
    return collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_by_date(report_date: date) -> dict | None:
    return get_collection().find_one({"report_date": report_date.isoformat()})


def already_sent(report_date: date) -> bool:
    doc = find_by_date(report_date)
    return bool(doc and doc.get("status") == STATUS_SENT)


def upsert_report(report_date: date, fields: dict[str, Any]) -> dict:
    """Insert or update the report record for a given date."""
    collection = get_collection()
    key = {"report_date": report_date.isoformat()}
    update = {"$set": {**fields, "updated_at": _now()}, "$setOnInsert": {"created_at": _now()}}
    collection.update_one(key, update, upsert=True)
    return collection.find_one(key)


def record_generation(
    report_date: date,
    stats: dict[str, Any],
    recipients: list[str],
    pdf_path: str,
) -> dict:
    """Store metrics for a generated (not yet sent) report."""
    return upsert_report(
        report_date,
        {
            "generated_time": _now(),
            "recipients": recipients,
            "articles_included": stats.get("total", 0),
            "problems_count": stats.get("problems", 0),
            "positive_count": stats.get("positive", 0),
            "negative_count": stats.get("negative", 0),
            "high_priority_problems": stats.get("high_priority_problems", 0),
            "pdf_path": pdf_path,
            "status": STATUS_PENDING,
        },
    )


def record_sent(report_date: date, retry_count: int) -> dict:
    return upsert_report(
        report_date,
        {"status": STATUS_SENT, "sent_time": _now(), "retry_count": retry_count, "error": None},
    )


def record_failed(report_date: date, retry_count: int, error: str) -> dict:
    return upsert_report(
        report_date,
        {"status": STATUS_FAILED, "retry_count": retry_count, "error": error},
    )


def history(limit: int = 60) -> list[dict]:
    """Return recent report records, newest first, JSON-serializable."""
    cursor = get_collection().find({}).sort("report_date", -1).limit(limit)
    return [_serialize(doc) for doc in cursor]


def get_by_id(report_id: str) -> dict | None:
    from bson import ObjectId
    from bson.errors import InvalidId

    collection = get_collection()
    doc = None
    try:
        doc = collection.find_one({"_id": ObjectId(report_id)})
    except (InvalidId, TypeError):
        doc = None
    if not doc:
        doc = collection.find_one({"report_date": report_id})
    return _serialize(doc) if doc else None


def _serialize(doc: dict) -> dict:
    result = dict(doc)
    if "_id" in result:
        result["_id"] = str(result["_id"])
    return result
