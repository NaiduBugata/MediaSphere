"""In-process news pipeline scheduler for Render Free web services.

Render Free does not support background workers. This module runs the Lokal +
YouTube pipeline inside the Flask process when ``PIPELINE_ON_API=true``.

Reliability guarantees:
- Single in-process APScheduler instance (idempotent ``start``).
- MongoDB ``scheduler_state`` for last_success (ephemeral disk is unused).
- MongoDB ``pipeline_lock`` so catch-up cannot race interval jobs / multi-process mistakes.
- Structured stage logging and pipeline history records.
"""

from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import lokal_collector
import pipeline_config
import pipeline_state
from run_all_pipelines import configure_logging, run_combined_cycle

logger = logging.getLogger("pipeline_scheduler")

_scheduler: BackgroundScheduler | None = None
_start_lock = threading.Lock()
_job_gate = threading.Lock()


def is_running() -> bool:
    return bool(_scheduler and _scheduler.running)


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _next_run_iso() -> str | None:
    if not _scheduler or not _scheduler.running:
        return None
    job = _scheduler.get_job(pipeline_config.JOB_ID)
    if not job or not job.next_run_time:
        return None
    nxt = job.next_run_time
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    return nxt.astimezone(timezone.utc).isoformat()


def run_self_test() -> dict[str, Any]:
    """Verify Mongo connectivity, indexes, and required config before scheduling."""
    result: dict[str, Any] = {
        "config_ok": False,
        "mongo_ok": False,
        "indexes_ok": False,
        "groq_keys": 0,
        "errors": [],
        "warnings": [],
    }

    validation = pipeline_config.validate_for_scheduler()
    result["config_ok"] = validation.ok
    result["errors"].extend(validation.errors)
    result["warnings"].extend(validation.warnings)
    result["groq_keys"] = len(pipeline_config.discover_groq_keys())

    if not validation.ok:
        return result

    try:
        ping = pipeline_state.ping_mongo()
        result["mongo_ok"] = bool(ping.get("ok"))
        result["mongo"] = {
            "latency_ms": ping.get("latency_ms"),
            "database": ping.get("database"),
            "articles_count": ping.get("articles_count"),
        }
        pipeline_state.ensure_indexes()
        result["indexes_ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"Mongo self-test failed: {exc}")
        result["mongo_ok"] = False
        result["indexes_ok"] = False

    return result


def _empty_stats() -> dict[str, Any]:
    return {
        "articles_fetched": 0,
        "duplicates": 0,
        "inserted": 0,
        "lokal_processed": 0,
        "youtube_processed": 0,
        "errors": [],
        "lokal": {},
        "youtube": {},
    }


def _job(trigger: str = "interval") -> None:
    """Run one locked pipeline cycle. Never raises (scheduler must not die)."""
    # Serialize catch-up vs interval within this process as a belt-and-suspenders
    # measure; Mongo lock covers cross-process races.
    if not _job_gate.acquire(blocking=False):
        logger.info("Pipeline job skipped: another cycle is already in progress (local gate).")
        return

    owner: str | None = None
    started = datetime.now(timezone.utc)
    started_perf = started
    stats = _empty_stats()
    status = "failed"
    errors: list[str] = []

    try:
        owner = pipeline_state.acquire_lock()
        if not owner:
            logger.info("Pipeline job skipped: distributed lock held by another instance.")
            return

        logger.info("Starting pipeline | trigger=%s | owner=%s", trigger, owner)
        logger.info("Collecting Lokal")
        logger.info("Collecting YouTube")
        logger.info("Categorizing")
        logger.info("Saving MongoDB")

        pipeline_state.update_state(
            {
                "last_run": started.isoformat(),
                "status": "running",
                "trigger": trigger,
            }
        )

        exit_code, stats = run_combined_cycle()
        errors = list(stats.get("errors") or [])
        finished = datetime.now(timezone.utc)
        duration = (finished - started_perf).total_seconds()

        if exit_code == 0:
            status = "success"
            pipeline_state.update_state(
                {
                    "last_run": started.isoformat(),
                    "last_success": finished.isoformat(),
                    "status": "success",
                    "duration_seconds": round(duration, 3),
                    "articles_inserted": int(stats.get("inserted") or 0),
                    "next_run": _next_run_iso(),
                    "last_errors": [],
                }
            )
            logger.info(
                "Finished successfully | duration=%.2fs | inserted=%s | duplicates=%s",
                duration,
                stats.get("inserted"),
                stats.get("duplicates"),
            )
            logger.info("Dashboard refresh available")
        else:
            status = "failed"
            errors.append(f"combined_cycle_exit_code={exit_code}")
            pipeline_state.update_state(
                {
                    "last_run": started.isoformat(),
                    "last_failure": finished.isoformat(),
                    "status": "failed",
                    "duration_seconds": round(duration, 3),
                    "articles_inserted": int(stats.get("inserted") or 0),
                    "next_run": _next_run_iso(),
                    "last_errors": errors[:20],
                }
            )
            logger.error(
                "Pipeline finished with failures | duration=%.2fs | errors=%s",
                duration,
                errors,
            )

        pipeline_state.record_history(
            {
                "start_time": started.isoformat(),
                "finish_time": finished.isoformat(),
                "duration_seconds": round(duration, 3),
                "articles_fetched": int(stats.get("articles_fetched") or 0),
                "duplicates": int(stats.get("duplicates") or 0),
                "inserted": int(stats.get("inserted") or 0),
                "lokal_processed": int(stats.get("lokal_processed") or 0),
                "youtube_processed": int(stats.get("youtube_processed") or 0),
                "errors": errors[:50],
                "status": status,
                "trigger": trigger,
            }
        )
    except Exception as exc:  # noqa: BLE001 - scheduler must never die
        finished = datetime.now(timezone.utc)
        duration = (finished - started_perf).total_seconds()
        tb = traceback.format_exc()
        logger.error("Scheduled pipeline cycle crashed: %s\n%s", exc, tb)
        errors.append(str(exc))
        try:
            pipeline_state.update_state(
                {
                    "last_run": started.isoformat(),
                    "last_failure": finished.isoformat(),
                    "status": "failed",
                    "duration_seconds": round(duration, 3),
                    "next_run": _next_run_iso(),
                    "last_errors": errors[:20],
                }
            )
            pipeline_state.record_history(
                {
                    "start_time": started.isoformat(),
                    "finish_time": finished.isoformat(),
                    "duration_seconds": round(duration, 3),
                    "articles_fetched": int(stats.get("articles_fetched") or 0),
                    "duplicates": int(stats.get("duplicates") or 0),
                    "inserted": int(stats.get("inserted") or 0),
                    "lokal_processed": int(stats.get("lokal_processed") or 0),
                    "youtube_processed": int(stats.get("youtube_processed") or 0),
                    "errors": errors[:50],
                    "status": "failed",
                    "trigger": trigger,
                }
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist pipeline failure state")
    finally:
        if owner:
            try:
                pipeline_state.release_lock(owner)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to release pipeline lock for owner=%s", owner)
        _job_gate.release()


def _catch_up() -> None:
    """Run one cycle on startup when last_success is missing or stale."""
    interval_seconds = lokal_collector.CHECK_INTERVAL
    try:
        state = pipeline_state.get_state()
        last_success = _parse_iso(state.get("last_success"))
        if last_success is not None:
            age = (datetime.now(timezone.utc) - last_success).total_seconds()
            if age < interval_seconds:
                logger.info(
                    "Catch-up skipped: last successful run was %.0f min ago (< interval).",
                    age / 60,
                )
                return
        logger.info("Catch-up: running pipeline cycle on startup.")
        _job(trigger="catch_up")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Catch-up failed: %s", exc)


def start(run_catch_up: bool = True) -> BackgroundScheduler | None:
    """Start the background pipeline scheduler (idempotent)."""
    global _scheduler

    with _start_lock:
        if _scheduler and _scheduler.running:
            logger.info("Scheduler already running.")
            return _scheduler

        configure_logging()

        self_test = run_self_test()
        logger.info("Pipeline self-test result: %s", self_test)
        if self_test.get("errors"):
            for err in self_test["errors"]:
                logger.error("Scheduler start aborted: %s", err)
            return None
        for warning in self_test.get("warnings") or []:
            logger.warning("%s", warning)

        interval_seconds = lokal_collector.CHECK_INTERVAL
        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            _job,
            trigger=IntervalTrigger(seconds=interval_seconds),
            kwargs={"trigger": "interval"},
            id=pipeline_config.JOB_ID,
            name="Lokal + YouTube news pipeline",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
        _scheduler.start()

        next_run = _next_run_iso()
        pipeline_state.update_state(
            {
                "status": "idle",
                "next_run": next_run,
                "scheduler": "running",
                "interval_seconds": interval_seconds,
            }
        )
        logger.info(
            "Scheduler initialized successfully. | interval: %s seconds (%.2f hours) | next_run=%s",
            interval_seconds,
            interval_seconds / 3600,
            next_run,
        )

    if run_catch_up:
        threading.Thread(target=_catch_up, name="pipeline-catch-up", daemon=True).start()

    return _scheduler


def run_now() -> None:
    """Manually trigger one locked cycle in a daemon thread (admin use)."""
    threading.Thread(target=_job, kwargs={"trigger": "manual"}, name="pipeline-manual", daemon=True).start()


def health_snapshot() -> dict[str, Any]:
    """Sanitized pipeline health for API clients."""
    state = {}
    lock = {}
    articles = None
    try:
        state = pipeline_state.get_state()
        lock = pipeline_state.get_lock_summary()
        articles = pipeline_state.article_count()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pipeline health state unavailable: %s", exc)

    return {
        "scheduler": "running" if is_running() else "stopped",
        "last_run": state.get("last_run"),
        "last_success": state.get("last_success"),
        "last_failure": state.get("last_failure"),
        "next_run": _next_run_iso() or state.get("next_run"),
        "status": state.get("status") or ("healthy" if is_running() else "stopped"),
        "articles_processed": articles,
        "last_duration_seconds": state.get("duration_seconds"),
        "articles_inserted_last_run": state.get("articles_inserted"),
        "lock": lock,
        "data_revision": state.get("last_success") or state.get("last_run"),
    }


def shutdown() -> None:
    global _scheduler
    with _start_lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("Pipeline scheduler stopped.")
        _scheduler = None
