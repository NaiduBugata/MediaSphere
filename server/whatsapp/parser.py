"""Parse WhatsApp Cloud API webhook payloads into normalized event records."""

from __future__ import annotations

from typing import Any

KNOWN_MESSAGE_TYPES = frozenset(
    {
        "text",
        "image",
        "document",
        "audio",
        "video",
        "sticker",
        "interactive",
        "button",
        "contacts",
        "location",
        "reaction",
        "order",
        "system",
        "unknown",
    }
)

KNOWN_STATUS_VALUES = frozenset({"sent", "delivered", "read", "failed"})


def _base_event(
    *,
    event_category: str,
    event_type: str,
    waba_id: str | None,
    phone_number_id: str | None,
    display_phone_number: str | None,
    change_field: str | None,
    raw_change: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_category": event_category,
        "event_type": event_type,
        "waba_id": waba_id,
        "phone_number_id": phone_number_id,
        "display_phone_number": display_phone_number,
        "change_field": change_field,
        "sender_wa_id": None,
        "sender_profile_name": None,
        "message_id": None,
        "message_timestamp": None,
        "message_text": None,
        "status": None,
        "error_codes": [],
        "media_ids": [],
        "interactive_response": None,
        "template_status": None,
        "raw_change": raw_change,
    }


def _contact_map(contacts: list[dict[str, Any]] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for contact in contacts or []:
        wa_id = contact.get("wa_id")
        profile = contact.get("profile") or {}
        name = profile.get("name")
        if wa_id:
            mapping[str(wa_id)] = str(name) if name else ""
    return mapping


def _extract_media_id(message: dict[str, Any], msg_type: str) -> str | None:
    block = message.get(msg_type)
    if isinstance(block, dict):
        media_id = block.get("id")
        return str(media_id) if media_id else None
    return None


def _extract_interactive(message: dict[str, Any]) -> dict[str, Any] | None:
    interactive = message.get("interactive")
    if isinstance(interactive, dict):
        response: dict[str, Any] = {"type": interactive.get("type")}
        if interactive.get("button_reply"):
            response["button_reply"] = interactive["button_reply"]
        if interactive.get("list_reply"):
            response["list_reply"] = interactive["list_reply"]
        return response

    button = message.get("button")
    if isinstance(button, dict):
        return {"type": "button", "button": button}
    return None


def _parse_message(
    message: dict[str, Any],
    *,
    waba_id: str | None,
    metadata: dict[str, Any],
    contacts: dict[str, str],
    change_field: str | None,
    raw_change: dict[str, Any],
) -> dict[str, Any]:
    msg_type = str(message.get("type") or "unknown")
    sender = str(message.get("from") or "")
    event = _base_event(
        event_category="message",
        event_type=msg_type if msg_type in KNOWN_MESSAGE_TYPES else "unknown",
        waba_id=waba_id,
        phone_number_id=metadata.get("phone_number_id"),
        display_phone_number=metadata.get("display_phone_number"),
        change_field=change_field,
        raw_change=raw_change,
    )
    event["sender_wa_id"] = sender or None
    event["sender_profile_name"] = contacts.get(sender) or None
    event["message_id"] = message.get("id")
    event["message_timestamp"] = message.get("timestamp")

    if msg_type == "text":
        text_block = message.get("text") or {}
        event["message_text"] = text_block.get("body")
    elif msg_type in {"image", "document", "audio", "video", "sticker"}:
        media_id = _extract_media_id(message, msg_type)
        if media_id:
            event["media_ids"] = [media_id]
    elif msg_type == "interactive":
        event["interactive_response"] = _extract_interactive(message)
        if event["interactive_response"]:
            reply = event["interactive_response"]
            if reply.get("button_reply"):
                event["message_text"] = reply["button_reply"].get("title")
            elif reply.get("list_reply"):
                event["message_text"] = reply["list_reply"].get("title")
    elif msg_type == "button":
        event["interactive_response"] = _extract_interactive(message)
        button = message.get("button") or {}
        event["message_text"] = button.get("text") or button.get("payload")
    elif msg_type == "contacts":
        event["message_text"] = str(message.get("contacts"))
    elif msg_type == "location":
        location = message.get("location") or {}
        event["message_text"] = (
            f"lat={location.get('latitude')}, lng={location.get('longitude')}, "
            f"name={location.get('name')}, address={location.get('address')}"
        )

    if event["event_type"] == "unknown":
        event["message_text"] = event["message_text"] or str(message)

    return event


def _parse_status(
    status: dict[str, Any],
    *,
    waba_id: str | None,
    metadata: dict[str, Any],
    change_field: str | None,
    raw_change: dict[str, Any],
) -> dict[str, Any]:
    status_value = str(status.get("status") or "unknown")
    event = _base_event(
        event_category="status",
        event_type=status_value if status_value in KNOWN_STATUS_VALUES else "unknown",
        waba_id=waba_id,
        phone_number_id=metadata.get("phone_number_id"),
        display_phone_number=metadata.get("display_phone_number"),
        change_field=change_field,
        raw_change=raw_change,
    )
    event["message_id"] = status.get("id")
    event["message_timestamp"] = status.get("timestamp")
    event["status"] = status_value
    event["sender_wa_id"] = status.get("recipient_id")

    errors = status.get("errors") or []
    error_codes: list[dict[str, Any]] = []
    for err in errors:
        if isinstance(err, dict):
            error_codes.append(
                {
                    "code": err.get("code"),
                    "title": err.get("title"),
                    "message": err.get("message"),
                    "details": err.get("error_data"),
                }
            )
    event["error_codes"] = error_codes
    return event


def _parse_template_status(
    template_update: dict[str, Any],
    *,
    waba_id: str | None,
    metadata: dict[str, Any],
    change_field: str | None,
    raw_change: dict[str, Any],
) -> dict[str, Any]:
    event = _base_event(
        event_category="template",
        event_type="message_template_status_update",
        waba_id=waba_id,
        phone_number_id=metadata.get("phone_number_id"),
        display_phone_number=metadata.get("display_phone_number"),
        change_field=change_field,
        raw_change=raw_change,
    )
    event["template_status"] = template_update
    event["message_id"] = template_update.get("message_template_id") or template_update.get("id")
    event["status"] = template_update.get("event") or template_update.get("status")
    return event


def _parse_value_change(
    change: dict[str, Any],
    *,
    waba_id: str | None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    value = change.get("value") or {}
    if not isinstance(value, dict):
        return events

    change_field = change.get("field")
    metadata = value.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    contacts = _contact_map(value.get("contacts"))

    for message in value.get("messages") or []:
        if isinstance(message, dict):
            events.append(
                _parse_message(
                    message,
                    waba_id=waba_id,
                    metadata=metadata,
                    contacts=contacts,
                    change_field=change_field,
                    raw_change=change,
                )
            )

    for status in value.get("statuses") or []:
        if isinstance(status, dict):
            events.append(
                _parse_status(
                    status,
                    waba_id=waba_id,
                    metadata=metadata,
                    change_field=change_field,
                    raw_change=change,
                )
            )

    template_update = value.get("message_template_status_update")
    if isinstance(template_update, dict):
        events.append(
            _parse_template_status(
                template_update,
                waba_id=waba_id,
                metadata=metadata,
                change_field=change_field,
                raw_change=change,
            )
        )

    for err in value.get("errors") or []:
        if isinstance(err, dict):
            event = _base_event(
                event_category="error",
                event_type="webhook_error",
                waba_id=waba_id,
                phone_number_id=metadata.get("phone_number_id"),
                display_phone_number=metadata.get("display_phone_number"),
                change_field=change_field,
                raw_change=change,
            )
            event["error_codes"] = [
                {
                    "code": err.get("code"),
                    "title": err.get("title"),
                    "message": err.get("message"),
                    "details": err.get("error_data"),
                }
            ]
            events.append(event)

    if not events and change_field:
        events.append(
            _base_event(
                event_category="unknown",
                event_type=str(change_field),
                waba_id=waba_id,
                phone_number_id=metadata.get("phone_number_id"),
                display_phone_number=metadata.get("display_phone_number"),
                change_field=change_field,
                raw_change=change,
            )
        )

    return events


def parse_webhook_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized events extracted from a Meta webhook POST body."""
    events: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return events

    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        waba_id = str(entry.get("id")) if entry.get("id") is not None else None
        for change in entry.get("changes") or []:
            if isinstance(change, dict):
                events.extend(_parse_value_change(change, waba_id=waba_id))

    if not events and payload:
        events.append(
            _base_event(
                event_category="unknown",
                event_type=str(payload.get("object") or "unknown"),
                waba_id=None,
                phone_number_id=None,
                display_phone_number=None,
                change_field=None,
                raw_change={"payload": payload},
            )
        )

    return events
