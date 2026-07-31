"""Outbound WhatsApp Cloud API messaging."""

from __future__ import annotations

import re
from typing import Any

import requests

from . import config
from .logger import log_event

_RECIPIENT_RE = re.compile(r"^\d{8,15}$")


class WhatsAppSendError(Exception):
    """Raised when a Graph API send request fails."""


def _error_reason(status_code: int, data: dict[str, Any]) -> str:
    error = data.get("error") if isinstance(data, dict) else {}
    code = error.get("code")
    subcode = error.get("error_subcode")

    if status_code == 401 or code in (190, 102):
        return "access_token_invalid_or_expired"
    if status_code == 429 or code == 4:
        return "rate_limited"
    if status_code >= 500:
        return "meta_server_error"
    if subcode:
        return f"meta_error_subcode_{subcode}"
    return "meta_api_error"


def _normalize_recipient(recipient: str) -> str:
    cleaned = recipient.strip().lstrip("+").replace(" ", "").replace("-", "")
    if not _RECIPIENT_RE.match(cleaned):
        raise ValueError(f"Invalid WhatsApp recipient: {recipient!r}")
    return cleaned


def send_text_message(recipient: str, message: str) -> dict[str, Any]:
    """Send a text message via WhatsApp Cloud API Graph endpoint."""
    if not config.WHATSAPP_ACCESS_TOKEN:
        raise WhatsAppSendError("WHATSAPP_ACCESS_TOKEN is not configured")
    if not message or not message.strip():
        raise ValueError("message must not be empty")

    to_number = _normalize_recipient(recipient)
    url = config.messages_endpoint()
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": False, "body": message.strip()},
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
    except requests.RequestException as exc:
        log_event(
            "error",
            event_category="outgoing_message",
            event_type="text",
            error=f"network_failure: {exc}",
            extra={"recipient": to_number, "endpoint": url},
        )
        raise WhatsAppSendError(str(exc)) from exc

    try:
        data = response.json()
    except ValueError as exc:
        log_event(
            "error",
            event_category="outgoing_message",
            event_type="text",
            error=f"non_json_response_http_{response.status_code}",
            extra={"recipient": to_number, "endpoint": url},
        )
        raise WhatsAppSendError(
            f"Graph API returned non-JSON response (HTTP {response.status_code})"
        ) from exc

    if not response.ok:
        error = data.get("error", {}) if isinstance(data, dict) else {}
        error_message = error.get("message") or response.text
        reason = _error_reason(response.status_code, data)
        log_event(
            "error",
            event_category="outgoing_message",
            event_type="text",
            error=reason,
            extra={
                "recipient": to_number,
                "endpoint": url,
                "http_status": response.status_code,
                "meta_error_code": error.get("code"),
                "meta_error_subcode": error.get("error_subcode"),
                "meta_error_message": error_message,
            },
        )
        err = WhatsAppSendError(f"Graph API error {response.status_code}: {error_message}")
        setattr(err, "status_code", response.status_code)
        setattr(err, "meta_error_code", error.get("code"))
        setattr(err, "meta_response", data)
        raise err

    message_id = None
    messages = data.get("messages") if isinstance(data, dict) else None
    if isinstance(messages, list) and messages:
        message_id = messages[0].get("id")

    log_event(
        "info",
        event_category="outgoing_message",
        event_type="text",
        message_id=message_id,
        extra={"recipient": to_number, "endpoint": url, "http_status": response.status_code},
    )
    return data


def send_template_message(
    recipient: str,
    template_name: str,
    *,
    language: str = "en",
    body_parameters: list[str] | None = None,
    components: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Send a WhatsApp Cloud API template message (business-initiated).

    Parameters:
        recipient: Phone number (digits / E.164 without +).
        template_name: Approved template name in Meta Business Manager.
        language: Template language code (e.g. ``en``, ``en_US``).
        body_parameters: Positional body variables mapped to ``{{1}}``, ``{{2}}``, …
        components: Optional raw Graph API ``components`` list (overrides body_parameters).
    """
    if not config.WHATSAPP_ACCESS_TOKEN:
        raise WhatsAppSendError("WHATSAPP_ACCESS_TOKEN is not configured")
    if not template_name or not template_name.strip():
        raise ValueError("template_name must not be empty")

    to_number = _normalize_recipient(recipient)
    url = config.messages_endpoint()
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    if components is None:
        params = body_parameters or []
        components = []
        if params:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)[:1024]} for p in params],
                }
            )

    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name.strip(),
            "language": {"code": (language or "en").strip()},
            "components": components,
        },
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
    except requests.RequestException as exc:
        log_event(
            "error",
            event_category="outgoing_message",
            event_type="template",
            error=f"network_failure: {exc}",
            extra={"recipient": to_number, "endpoint": url, "template": template_name},
        )
        raise WhatsAppSendError(str(exc)) from exc

    try:
        data = response.json()
    except ValueError as exc:
        log_event(
            "error",
            event_category="outgoing_message",
            event_type="template",
            error=f"non_json_response_http_{response.status_code}",
            extra={"recipient": to_number, "endpoint": url, "template": template_name},
        )
        raise WhatsAppSendError(
            f"Graph API returned non-JSON response (HTTP {response.status_code})"
        ) from exc

    if not response.ok:
        error = data.get("error", {}) if isinstance(data, dict) else {}
        error_message = error.get("message") or response.text
        reason = _error_reason(response.status_code, data)
        log_event(
            "error",
            event_category="outgoing_message",
            event_type="template",
            error=reason,
            extra={
                "recipient": to_number,
                "endpoint": url,
                "template": template_name,
                "http_status": response.status_code,
                "meta_error_code": error.get("code"),
                "meta_error_subcode": error.get("error_subcode"),
                "meta_error_message": error_message,
            },
        )
        err = WhatsAppSendError(f"Graph API error {response.status_code}: {error_message}")
        setattr(err, "status_code", response.status_code)
        setattr(err, "meta_error_code", error.get("code"))
        setattr(err, "meta_response", data)
        raise err

    message_id = None
    messages = data.get("messages") if isinstance(data, dict) else None
    if isinstance(messages, list) and messages:
        message_id = messages[0].get("id")

    log_event(
        "info",
        event_category="outgoing_message",
        event_type="template",
        message_id=message_id,
        extra={
            "recipient": to_number,
            "endpoint": url,
            "template": template_name,
            "http_status": response.status_code,
        },
    )
    return data
