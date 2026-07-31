"""Structured JSON logging for WhatsApp webhook events."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

SERVICE_NAME = "whatsapp_webhook"

_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "proxy-authorization",
    }
)

_logger = logging.getLogger(SERVICE_NAME)


def get_logger(name: str = SERVICE_NAME) -> logging.Logger:
    return logging.getLogger(name)


def sanitize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    if not headers:
        return {}
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADERS:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = str(value)
    return sanitized


def log_event(
    level: str,
    *,
    client_ip: str | None = None,
    headers: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    event_category: str | None = None,
    event_type: str | None = None,
    message_id: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": SERVICE_NAME,
        "level": level.upper(),
        "client_ip": client_ip,
        "headers": sanitize_headers(headers),
        "payload": payload,
        "event_category": event_category,
        "event_type": event_type,
        "message_id": message_id,
        "error": error,
    }
    if extra:
        record.update(extra)

    line = json.dumps(record, ensure_ascii=False, default=str)
    log_fn = getattr(_logger, level.lower(), _logger.info)
    log_fn(line)
