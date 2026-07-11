"""Outbound WhatsApp Cloud API messaging."""

from __future__ import annotations

import re
from typing import Any

import requests

from . import config
from .logger import get_logger

logger = get_logger("whatsapp.send")

_RECIPIENT_RE = re.compile(r"^\d{8,15}$")


class WhatsAppSendError(Exception):
    """Raised when a Graph API send request fails."""


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
        logger.error("WhatsApp send request failed for recipient=%s: %s", to_number, exc)
        raise WhatsAppSendError(str(exc)) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise WhatsAppSendError(
            f"Graph API returned non-JSON response (HTTP {response.status_code})"
        ) from exc

    if not response.ok:
        error_message = data.get("error", {}).get("message") or response.text
        logger.error(
            "WhatsApp send failed recipient=%s status=%s error=%s",
            to_number,
            response.status_code,
            error_message,
        )
        raise WhatsAppSendError(f"Graph API error {response.status_code}: {error_message}")

    logger.info("WhatsApp text message sent to recipient=%s message_id=%s", to_number, data)
    return data
