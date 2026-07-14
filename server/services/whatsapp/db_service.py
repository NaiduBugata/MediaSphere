"""Persist WhatsApp webhook events to MongoDB via the shared mongo_store client."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

import mongo_store

from .logger import get_logger

logger = get_logger("whatsapp.db")

COLLECTION_NAME = "whatsapp_webhook_events"
_index_lock = threading.Lock()
_indexes_ready = False


def get_collection() -> Collection:
    global _indexes_ready

    client = mongo_store.get_client()
    collection = client[mongo_store.MONGODB_DB_NAME][COLLECTION_NAME]
    if not _indexes_ready:
        with _index_lock:
            if not _indexes_ready:
                collection.create_index("message_id")
                collection.create_index("received_at")
                collection.create_index("event_category")
                collection.create_index([("message_id", 1), ("event_category", 1), ("status", 1)])
                _indexes_ready = True
    return collection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedup_key(event: dict[str, Any]) -> dict[str, Any]:
    key: dict[str, Any] = {
        "event_category": event.get("event_category"),
        "event_type": event.get("event_type"),
    }
    message_id = event.get("message_id")
    if message_id:
        key["message_id"] = message_id
    status = event.get("status")
    if status:
        key["status"] = status
    sender = event.get("sender_wa_id")
    if sender and not message_id:
        key["sender_wa_id"] = sender
    timestamp = event.get("message_timestamp")
    if timestamp and not message_id:
        key["message_timestamp"] = timestamp
    return key


def save_event(
    event: dict[str, Any],
    *,
    client_ip: str | None,
    raw_payload: dict[str, Any],
) -> None:
    """Upsert a parsed webhook event. Failures are logged, never raised to caller."""
    try:
        collection = get_collection()
        now = _now()
        document = {
            **event,
            "client_ip": client_ip,
            "raw_payload": raw_payload,
            "received_at": now,
            "updated_at": now,
        }
        key = _dedup_key(event)
        collection.update_one(
            key,
            {"$set": document, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except Exception as exc:
        logger.error(
            "Failed to persist WhatsApp event message_id=%s: %s",
            event.get("message_id"),
            exc,
        )
