"""Notification service — thin shim to the Notification Manager."""

from __future__ import annotations

import logging

logger = logging.getLogger("services.notification")


def send_incremental_notifications() -> dict:
    """Send Email + WhatsApp notifications for newly collected articles."""
    try:
        from notifications import get_notification_manager

        return get_notification_manager().notify_new_article(async_=False)
    except Exception as exc:
        logger.error("Incremental notification failed: %s", exc)
        return {"status": "error", "error": str(exc)}
