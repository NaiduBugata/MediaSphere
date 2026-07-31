"""Notification service — incremental email notifications for new articles."""

from __future__ import annotations

import logging

logger = logging.getLogger("services.notification")


def send_incremental_notifications() -> dict:
    """Send email notifications for newly collected articles not yet emailed."""
    from reports import config as report_config

    if not report_config.EMAIL_ENABLED:
        return {"status": "skipped", "reason": "email disabled"}

    try:
        from reports import incremental

        return incremental.send_incremental_report()
    except Exception as exc:
        logger.error("Incremental notification failed: %s", exc)
        return {"status": "error", "error": str(exc)}
