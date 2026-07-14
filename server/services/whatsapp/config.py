"""WhatsApp Cloud API configuration from environment variables."""

from __future__ import annotations

import os


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_WABA_ID = os.getenv("WHATSAPP_WABA_ID", "")
WHATSAPP_GRAPH_API_VERSION = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0")
WHATSAPP_WEBHOOK_ENABLED = _truthy("WHATSAPP_WEBHOOK_ENABLED", "true")


def graph_api_base_url() -> str:
    return f"https://graph.facebook.com/{WHATSAPP_GRAPH_API_VERSION}"


def messages_endpoint() -> str:
    if not WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError("WHATSAPP_PHONE_NUMBER_ID is not configured")
    return f"{graph_api_base_url()}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
