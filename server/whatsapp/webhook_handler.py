"""Orchestrate WhatsApp webhook POST processing."""

from __future__ import annotations

from typing import Any

from . import config
from . import db_service
from . import parser
from .logger import log_event

EXPECTED_OBJECT = "whatsapp_business_account"


def process_webhook_post(
    payload: dict[str, Any] | None,
    *,
    client_ip: str | None,
    headers: dict[str, Any] | None,
) -> tuple[str, int]:
    """
    Process an inbound Meta webhook POST.

    Returns:
        (response_body, http_status_code)
    """
    if payload is None:
        log_event(
            "error",
            client_ip=client_ip,
            headers=headers,
            error="Invalid or missing JSON payload",
        )
        return "Invalid JSON payload", 400

    if not isinstance(payload, dict):
        log_event(
            "error",
            client_ip=client_ip,
            headers=headers,
            payload={"value": str(payload)},
            error="Payload must be a JSON object",
        )
        return "Invalid JSON payload", 400

    log_event(
        "info",
        client_ip=client_ip,
        headers=headers,
        payload=payload,
        event_category="webhook",
        event_type="received",
    )

    object_type = payload.get("object")
    if object_type != EXPECTED_OBJECT:
        log_event(
            "warning",
            client_ip=client_ip,
            headers=headers,
            payload=payload,
            event_category="webhook",
            event_type="unexpected_object",
            error=f"Expected object={EXPECTED_OBJECT}, got {object_type!r}",
        )

    if config.WHATSAPP_WABA_ID:
        entry_ids = [
            str(entry.get("id"))
            for entry in (payload.get("entry") or [])
            if isinstance(entry, dict) and entry.get("id") is not None
        ]
        if entry_ids and config.WHATSAPP_WABA_ID not in entry_ids:
            log_event(
                "warning",
                client_ip=client_ip,
                headers=headers,
                payload=payload,
                event_category="webhook",
                event_type="waba_mismatch",
                error=f"Expected WABA ID {config.WHATSAPP_WABA_ID}, got {entry_ids}",
            )

    try:
        events = parser.parse_webhook_payload(payload)
    except Exception as exc:
        log_event(
            "error",
            client_ip=client_ip,
            headers=headers,
            payload=payload,
            error=f"Fatal parse error: {exc}",
        )
        return "Invalid JSON payload", 400

    for event in events:
        try:
            if event.get("event_category") == "unknown":
                log_event(
                    "warning",
                    client_ip=client_ip,
                    headers=headers,
                    payload=payload,
                    event_category=event.get("event_category"),
                    event_type=event.get("event_type"),
                    message_id=event.get("message_id"),
                    error="Unknown webhook event type",
                )
            else:
                log_event(
                    "info",
                    client_ip=client_ip,
                    headers=headers,
                    payload=payload,
                    event_category=event.get("event_category"),
                    event_type=event.get("event_type"),
                    message_id=event.get("message_id"),
                    extra={
                        "sender_wa_id": event.get("sender_wa_id"),
                        "status": event.get("status"),
                        "message_text": event.get("message_text"),
                    },
                )

            db_service.save_event(event, client_ip=client_ip, raw_payload=payload)
        except Exception as exc:
            log_event(
                "error",
                client_ip=client_ip,
                headers=headers,
                payload=payload,
                event_category=event.get("event_category"),
                event_type=event.get("event_type"),
                message_id=event.get("message_id"),
                error=f"Event processing error: {exc}",
            )

    return "EVENT_RECEIVED", 200
