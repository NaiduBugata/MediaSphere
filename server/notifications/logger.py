"""Structured logging helpers for notification delivery."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any


def get_logger(name: str = "notifications") -> logging.Logger:
    return logging.getLogger(name)


def log_delivery(
    *,
    channel: str,
    recipient: str,
    template: str | None,
    message_id: str | None,
    latency_ms: float | None,
    http_code: int | None,
    retries: int,
    status: str,
    notification_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured delivery log line."""
    logger = get_logger("notifications.delivery")
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "recipient": recipient,
        "template": template,
        "message_id": message_id,
        "latency_ms": latency_ms,
        "http_code": http_code,
        "retries": retries,
        "status": status,
        "notification_type": notification_type,
    }
    if extra:
        payload.update(extra)
    logger.info("notification_delivery %s", payload)
