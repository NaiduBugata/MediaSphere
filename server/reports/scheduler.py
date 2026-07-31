"""Production-ready scheduler for the daily report.

- Runs every day at 07:00 IST (configurable) via APScheduler.
- On startup, performs a one-time catch-up: if the report that should already
  have been delivered (based on the last scheduled 07:00 window) was missed,
  it is generated and sent immediately.
- De-duplication (in db_service) guarantees no day is emailed twice.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, time, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import config, db_service, report_generator
from .logger import get_logger

logger = get_logger("reports.scheduler")

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _expected_report_date(now: datetime | None = None) -> date:
    """Report date that should already have been delivered by the last 07:00 run."""
    now = (now or datetime.now(config.REPORT_TIMEZONE)).astimezone(config.REPORT_TIMEZONE)
    scheduled_today = time(hour=config.REPORT_HOUR, minute=config.REPORT_MINUTE)
    if now.time() >= scheduled_today:
        # Today's 07:00 window has passed -> it covers yesterday.
        return (now - timedelta(days=1)).date()
    # Before today's 07:00 -> last delivered window was yesterday, covering day-before.
    return (now - timedelta(days=2)).date()


def _scheduled_job() -> None:
    """The cron job body: generate & send yesterday's report."""
    logger.info("Scheduled 07:00 IST job triggered.")
    try:
        result = report_generator.generate_and_send()
        logger.info("Scheduled report result: %s", result.get("status"))
    except Exception as exc:  # noqa: BLE001 - scheduler must never die
        logger.exception("Scheduled report job crashed: %s", exc)


def _catch_up() -> None:
    """Send a missed report once, if the last scheduled window was not delivered."""
    try:
        target = _expected_report_date()
        if db_service.already_sent(target):
            logger.info("Catch-up: report for %s already delivered.", target.isoformat())
            return
        logger.info("Catch-up: missed report detected for %s; sending now.", target.isoformat())
        result = report_generator.generate_and_send(target)
        logger.info("Catch-up report result: %s", result.get("status"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Catch-up run failed: %s", exc)


def start(run_catch_up: bool = True) -> BackgroundScheduler | None:
    """Start the background scheduler (idempotent)."""
    global _scheduler

    if not config.REPORT_ENABLED:
        logger.info("Daily report scheduler disabled (REPORT_ENABLED=false).")
        return None

    with _lock:
        if _scheduler and _scheduler.running:
            logger.info("Scheduler already running.")
            return _scheduler

        _scheduler = BackgroundScheduler(timezone=config.REPORT_TIMEZONE)
        _scheduler.add_job(
            _scheduled_job,
            trigger=CronTrigger(
                hour=config.REPORT_HOUR,
                minute=config.REPORT_MINUTE,
                timezone=config.REPORT_TIMEZONE,
            ),
            id="daily_report",
            name="Daily Constituency Intelligence Report",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
        _scheduler.start()
        logger.info(
            "Daily report scheduler started (%02d:%02d %s).",
            config.REPORT_HOUR,
            config.REPORT_MINUTE,
            config.REPORT_TIMEZONE_NAME,
        )

    if run_catch_up:
        # Run catch-up off the main thread so app startup is not blocked.
        threading.Thread(target=_catch_up, name="report-catch-up", daemon=True).start()

    return _scheduler


def shutdown() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("Daily report scheduler stopped.")
        _scheduler = None
