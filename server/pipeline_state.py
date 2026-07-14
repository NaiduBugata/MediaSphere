"""MongoDB persistence for pipeline scheduler state, locks, and history.

Reuses the shared ``mongo_store`` client — no second Mongo connection.
"""

from __future__ import annotations

import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

import mongo_store
import pipeline_config
from retry_utils import retry_call

STATE_COLLECTION = "scheduler_state"
LOCK_COLLECTION = "pipeline_lock"
HISTORY_COLLECTION = "pipeline_history"

_indexes_ready = False
_index_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _db():
    return mongo_store.get_client()[mongo_store.MONGODB_DB_NAME]


def state_collection() -> Collection:
    return _db()[STATE_COLLECTION]


def lock_collection() -> Collection:
    return _db()[LOCK_COLLECTION]


def history_collection() -> Collection:
    return _db()[HISTORY_COLLECTION]


def ensure_indexes() -> None:
    """Create indexes once per process."""
    global _indexes_ready
    if _indexes_ready:
        return
    with _index_lock:
        if _indexes_ready:
            return

        def _create() -> None:
            history_collection().create_index([("start_time", -1)])
            history_collection().create_index("status")
            lock_collection().create_index("expires_at")

        retry_call(_create, label="pipeline_state.ensure_indexes")
        _indexes_ready = True


def get_state() -> dict[str, Any]:
    ensure_indexes()
    doc = state_collection().find_one({"_id": pipeline_config.PIPELINE_STATE_ID})
    return dict(doc) if doc else {"_id": pipeline_config.PIPELINE_STATE_ID}


def update_state(fields: dict[str, Any]) -> dict[str, Any]:
    ensure_indexes()
    payload = {**fields, "updated_at": _now_iso()}
    state_collection().update_one(
        {"_id": pipeline_config.PIPELINE_STATE_ID},
        {"$set": payload, "$setOnInsert": {"created_at": _now_iso()}},
        upsert=True,
    )
    return get_state()


def get_data_revision() -> str | None:
    state = get_state()
    return state.get("last_success") or state.get("last_run")


def article_count() -> int:
    return mongo_store.get_collection().count_documents({})


def new_lock_owner() -> str:
    host = socket.gethostname() or "host"
    return f"{host}:{uuid.uuid4().hex[:12]}"


def acquire_lock(owner: str | None = None, ttl_seconds: int | None = None) -> str | None:
    """
    Acquire the distributed pipeline lock.

    Returns the owner token on success, or None if another holder is active.
    """
    ensure_indexes()
    owner = owner or new_lock_owner()
    ttl = ttl_seconds if ttl_seconds is not None else pipeline_config.PIPELINE_LOCK_TTL_SECONDS
    now = _now()
    expires = now + timedelta(seconds=ttl)

    payload = {
        "owner": owner,
        "acquired_at": now,
        "expires_at": expires,
        "updated_at": now,
    }

    def _acquire() -> str | None:
        doc = lock_collection().find_one_and_update(
            {
                "_id": pipeline_config.PIPELINE_STATE_ID,
                "$or": [
                    {"owner": {"$exists": False}},
                    {"owner": None},
                    {"expires_at": {"$lte": now}},
                ],
            },
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
        if doc and doc.get("owner") == owner:
            return owner
        try:
            lock_collection().insert_one({"_id": pipeline_config.PIPELINE_STATE_ID, **payload})
            return owner
        except DuplicateKeyError:
            return None

    return retry_call(_acquire, label="pipeline_lock.acquire")


def release_lock(owner: str) -> bool:
    """Release the lock only if ``owner`` still holds it."""
    ensure_indexes()
    result = lock_collection().update_one(
        {"_id": pipeline_config.PIPELINE_STATE_ID, "owner": owner},
        {
            "$set": {
                "owner": None,
                "released_at": _now(),
                "updated_at": _now(),
            }
        },
    )
    return result.modified_count > 0


def get_lock_summary() -> dict[str, Any]:
    ensure_indexes()
    doc = lock_collection().find_one({"_id": pipeline_config.PIPELINE_STATE_ID}) or {}
    expires = doc.get("expires_at")
    held = bool(doc.get("owner")) and isinstance(expires, datetime) and expires > _now()
    return {
        "held": held,
        "owner_present": bool(doc.get("owner")),
        "expires_at": expires.isoformat() if isinstance(expires, datetime) else None,
        "acquired_at": doc["acquired_at"].isoformat()
        if isinstance(doc.get("acquired_at"), datetime)
        else None,
    }


def record_history(record: dict[str, Any]) -> str:
    ensure_indexes()
    payload = {**record, "recorded_at": _now_iso()}
    result = history_collection().insert_one(payload)
    return str(result.inserted_id)


def ping_mongo() -> dict[str, Any]:
    """Return latency diagnostics without exposing connection URIs."""
    started = _now()
    client = mongo_store.get_client()
    client.admin.command("ping")
    elapsed_ms = (_now() - started).total_seconds() * 1000
    return {
        "ok": True,
        "latency_ms": round(elapsed_ms, 2),
        "database": mongo_store.MONGODB_DB_NAME,
        "articles_collection": mongo_store.MONGODB_COLLECTION,
        "articles_count": article_count(),
    }
