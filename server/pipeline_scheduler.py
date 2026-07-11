"""In-process scheduler that runs the news pipeline on the API web service.

Render's free tier does not support background workers, so the Lokal + YouTube
pipeline cannot run as a separate ``run_all_pipelines.py`` worker there. This
module runs the same combined cycle inside the Flask web process instead:

- Every ``PIPELINE_INTERVAL_HOURS`` (via APScheduler) while the service is awake.
- Once shortly after startup (catch-up), so freshly published articles are
  collected without any manual step.

Enable by setting ``PIPELINE_ON_API=true``. gunicorn MUST run a single worker
(``--workers 1``) so only one scheduler instance exists; otherwise each worker
would run its own duplicate cycle.

Note: Free web services sleep after ~15 min without inbound traffic. The
dashboard's 5-minute polling keeps an open tab's service awake; on a cold wake
the catch-up run collects anything published while it slept.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import lokal_collector
from config import OUTPUT_PATH
from run_all_pipelines import configure_logging, run_combined_cycle

logger = logging.getLogger("pipeline_scheduler")

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()
_LAST_RUN_FILE = OUTPUT_PATH / "pipeline_last_run.json"


def _read_last_run() -> datetime | None:
    try:
        data = json.loads(_LAST_RUN_FILE.read_text(encoding="utf-8"))
        return datetime.fromisoformat(data["last_run"])
    except Exception:
        return None


def _write_last_run() -> None:
    try:
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        _LAST_RUN_FILE.write_text(
            json.dumps({"last_run": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - marker is best-effort
        logger.warning("Could not persist pipeline last-run marker: %s", exc)


def _job() -> None:
    """Run one combined pipeline cycle; never raise (scheduler must not die)."""
    try:
        run_combined_cycle()
        _write_last_run()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduled pipeline cycle crashed: %s", exc)


def _catch_up() -> None:
    """Run one cycle on startup unless a recent run already covered this window."""
    interval_seconds = lokal_collector.CHECK_INTERVAL
    last_run = _read_last_run()
    if last_run is not None:
        age = (datetime.now(timezone.utc) - last_run).total_seconds()
        if age < interval_seconds:
            logger.info(
                "Catch-up skipped: last pipeline run was %.0f min ago (< interval).",
                age / 60,
            )
            return
    logger.info("Catch-up: running pipeline cycle on startup.")
    _job()


def start(run_catch_up: bool = True) -> BackgroundScheduler | None:
    """Start the background pipeline scheduler (idempotent)."""
    global _scheduler

    with _lock:
        if _scheduler and _scheduler.running:
            logger.info("Pipeline scheduler already running.")
            return _scheduler

        configure_logging()
        interval_seconds = lokal_collector.CHECK_INTERVAL

        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            _job,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="news_pipeline",
            name="Lokal + YouTube news pipeline",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
        _scheduler.start()
        logger.info(
            "Pipeline scheduler started | interval: %s seconds (%.2f hours).",
            interval_seconds,
            interval_seconds / 3600,
        )

    if run_catch_up:
        threading.Thread(target=_catch_up, name="pipeline-catch-up", daemon=True).start()

    return _scheduler


def shutdown() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("Pipeline scheduler stopped.")
        _scheduler = None
