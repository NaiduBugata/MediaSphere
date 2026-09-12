"""Admin fetch monitoring — aggregates pipeline_state + history (single fetch pipeline)."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pipeline_config
import pipeline_state

logger = logging.getLogger("admin.fetch")


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def fetch_interval_hours() -> float:
    if os.getenv("FETCH_INTERVAL_HOURS", "").strip():
        return max(0.1, _float_env("FETCH_INTERVAL_HOURS", pipeline_config.PIPELINE_INTERVAL_HOURS))
    return max(0.1, float(pipeline_config.PIPELINE_INTERVAL_HOURS))


def delay_tolerance_minutes() -> int:
    return max(1, _int_env("FETCH_DELAY_TOLERANCE_MINUTES", 30))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _ago_seconds(iso: str | None) -> float | None:
    dt = _parse_iso(iso)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())


def _public_run(doc: dict[str, Any]) -> dict[str, Any]:
    oid = doc.get("_id")
    errors = doc.get("errors") or []
    err_msg = None
    if errors:
        err_msg = "; ".join(str(e) for e in errors[:5])
    elif doc.get("error_message"):
        err_msg = str(doc.get("error_message"))[:500]

    trigger = (doc.get("trigger") or "automatic").lower()
    if trigger in ("interval", "catch_up", "automatic"):
        trigger_label = "automatic"
    elif trigger == "manual":
        trigger_label = "manual"
    elif trigger == "retry":
        trigger_label = "retry"
    else:
        trigger_label = trigger

    status = doc.get("status") or "unknown"
    if status in ("failed", "error"):
        status = "failed"

    return {
        "id": str(oid) if oid is not None else None,
        "run_id": doc.get("run_id") or (str(oid) if oid is not None else None),
        "trigger": trigger_label,
        "trigger_raw": doc.get("trigger"),
        "status": status,
        "started_at": doc.get("start_time"),
        "completed_at": doc.get("finish_time"),
        "duration_seconds": doc.get("duration_seconds"),
        "records_fetched": doc.get("articles_fetched") or 0,
        "records_processed": (
            int(doc.get("lokal_processed") or 0)
            + int(doc.get("youtube_processed") or 0)
            + int(doc.get("sakshi_processed") or 0)
        ),
        "records_inserted": doc.get("inserted") or 0,
        "duplicates": doc.get("duplicates") or 0,
        "error_message": err_msg,
        "errors": errors[:20] if isinstance(errors, list) else [],
        "retry_count": int(doc.get("retry_count") or 0),
        "parent_run_id": doc.get("parent_run_id"),
    }


def list_history(
    *,
    limit: int = 50,
    status: str | None = None,
    trigger: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    pipeline_state.ensure_indexes()
    query: dict[str, Any] = {}
    if status:
        st = status.lower()
        if st == "success":
            query["status"] = "success"
        elif st == "failed":
            query["status"] = {"$in": ["failed", "error", "timeout"]}
        elif st in ("skipped", "running", "timeout", "cancelled"):
            query["status"] = st
        else:
            query["status"] = status
    if trigger:
        tr = trigger.lower()
        if tr == "automatic":
            query["trigger"] = {"$in": ["interval", "catch_up", "automatic"]}
        elif tr in ("manual", "retry"):
            query["trigger"] = tr
        else:
            query["trigger"] = trigger

    cursor = (
        pipeline_state.history_collection()
        .find(query)
        .sort("start_time", -1)
        .limit(max(1, min(limit, 200)))
    )
    rows = [_public_run(doc) for doc in cursor]
    if q:
        needle = q.lower()
        rows = [
            r
            for r in rows
            if needle in (r.get("error_message") or "").lower()
            or needle in (r.get("run_id") or "").lower()
            or needle in (r.get("status") or "").lower()
        ]
    return rows


def get_run(run_id: str) -> dict[str, Any] | None:
    pipeline_state.ensure_indexes()
    coll = pipeline_state.history_collection()
    doc = coll.find_one({"run_id": run_id})
    if not doc:
        try:
            from bson import ObjectId

            doc = coll.find_one({"_id": ObjectId(run_id)})
        except Exception:  # noqa: BLE001
            doc = None
    return _public_run(doc) if doc else None


def history_stats() -> dict[str, int]:
    pipeline_state.ensure_indexes()
    coll = pipeline_state.history_collection()
    success = coll.count_documents({"status": "success"})
    failed = coll.count_documents({"status": {"$in": ["failed", "error", "timeout"]}})
    skipped = coll.count_documents({"status": "skipped"})
    running = coll.count_documents({"status": "running"})
    return {
        "successful": int(success),
        "failed": int(failed),
        "skipped": int(skipped),
        "running": int(running),
        "total": int(success + failed + skipped + running),
    }


def build_admin_status() -> dict[str, Any]:
    import pipeline_scheduler

    snapshot = pipeline_scheduler.health_snapshot()
    lock = snapshot.get("lock") or {}
    last_success = snapshot.get("last_success")
    last_run = snapshot.get("last_run")
    last_failure = snapshot.get("last_failure")
    next_run = snapshot.get("next_run")
    interval_h = fetch_interval_hours()
    tolerance_m = delay_tolerance_minutes()
    age_s = _ago_seconds(last_success)
    interval_s = interval_h * 3600
    delayed = False
    delay_seconds = 0.0
    if age_s is None:
        headline = "never_fetched"
    elif lock.get("held") or (snapshot.get("status") == "running"):
        headline = "running"
    elif snapshot.get("status") == "failed" and last_failure and (
        not last_success or str(last_failure) > str(last_success)
    ):
        headline = "failed"
    elif age_s > interval_s + (tolerance_m * 60):
        headline = "scheduler_delayed"
        delayed = True
        delay_seconds = age_s - interval_s
    else:
        headline = "healthy"

    freshness = "unknown"
    if age_s is not None:
        if age_s <= interval_s:
            freshness = "fresh"
        elif age_s <= interval_s + (tolerance_m * 60):
            freshness = "aging"
        else:
            freshness = "stale"

    stats = history_stats()
    alerts: list[dict[str, str]] = []
    if headline == "failed":
        alerts.append(
            {
                "level": "critical",
                "code": "fetch_failed",
                "message": "The latest automatic/manual fetch failed.",
            }
        )
    if delayed or headline == "scheduler_delayed":
        alerts.append(
            {
                "level": "warning",
                "code": "scheduler_delayed",
                "message": (
                    f"No successful fetch within the expected {interval_h:g}h interval "
                    f"(+{tolerance_m}m tolerance)."
                ),
            }
        )
    if headline == "running":
        alerts.append(
            {
                "level": "info",
                "code": "fetch_running",
                "message": "A fetch operation is currently running.",
            }
        )
    if headline == "never_fetched":
        alerts.append(
            {
                "level": "warning",
                "code": "never_fetched",
                "message": "No successful fetch has been recorded yet.",
            }
        )

    return {
        "headline": headline,
        "scheduler": snapshot.get("scheduler"),
        "status": snapshot.get("status"),
        "lock": lock,
        "last_run": last_run,
        "last_success": last_success,
        "last_failure": last_failure,
        "next_run": next_run,
        "last_duration_seconds": snapshot.get("last_duration_seconds"),
        "articles_inserted_last_run": snapshot.get("articles_inserted_last_run"),
        "articles_count": snapshot.get("articles_processed"),
        "data_revision": pipeline_state.get_data_revision(),
        "sources": snapshot.get("sources"),
        "interval_hours": interval_h,
        "delay_tolerance_minutes": tolerance_m,
        "data_age_seconds": age_s,
        "scheduler_delayed": delayed,
        "delay_seconds": delay_seconds if delayed else 0,
        "freshness": freshness,
        "stats": stats,
        "alerts": alerts,
        "pipeline_on_api": bool(pipeline_config.PIPELINE_ON_API),
        "admin_token_configured": bool(pipeline_config.PIPELINE_ADMIN_TOKEN),
    }


def build_health_check() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        ping = pipeline_state.ping_mongo()
        checks["database"] = {"ok": True, "latency_ms": ping.get("latency_ms")}
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"ok": False, "error": str(exc)[:200]}

    import pipeline_scheduler

    checks["application"] = {"ok": True}
    checks["scheduler"] = {
        "ok": pipeline_scheduler.is_running() or not pipeline_config.PIPELINE_ON_API,
        "running": pipeline_scheduler.is_running(),
        "pipeline_on_api": bool(pipeline_config.PIPELINE_ON_API),
    }
    status = build_admin_status()
    age = status.get("data_age_seconds")
    checks["latest_data"] = {
        "ok": age is not None
        and age <= (fetch_interval_hours() * 3600 + delay_tolerance_minutes() * 60),
        "age_seconds": age,
        "freshness": status.get("freshness"),
    }
    checks["data_source"] = {
        "ok": all(v in ("healthy", "disabled") for v in (status.get("sources") or {}).values()),
        "sources": status.get("sources"),
    }
    overall = all(bool(c.get("ok")) for c in checks.values())
    return {"ok": overall, "checks": checks}


def new_run_id() -> str:
    return f"fetch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def trigger_fetch(*, trigger: str = "manual", parent_run_id: str | None = None) -> dict[str, Any]:
    """Start the shared pipeline cycle (same path as the scheduler)."""
    import pipeline_scheduler

    lock = pipeline_state.get_lock_summary()
    if lock.get("held"):
        return {
            "accepted": False,
            "status": "already_running",
            "message": "A fetch operation is already running.",
            "lock": lock,
        }

    run_id = new_run_id()
    pipeline_state.update_state(
        {
            "status": "running",
            "trigger": trigger,
            "pending_run_id": run_id,
            "pending_parent_run_id": parent_run_id,
        }
    )
    pipeline_scheduler.run_now(trigger=trigger, run_id=run_id, parent_run_id=parent_run_id)
    return {
        "accepted": True,
        "status": "accepted",
        "message": "Pipeline cycle triggered",
        "run_id": run_id,
        "trigger": trigger,
    }
