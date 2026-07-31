"""Notification framework configuration from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default) or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---- Feature flags ----
EMAIL_ENABLED = _truthy("EMAIL_ENABLED", "false")
WHATSAPP_ENABLED = _truthy("WHATSAPP_ENABLED", "false")
WHATSAPP_USE_TEMPLATES = _truthy("WHATSAPP_USE_TEMPLATES", "true")

# ---- WhatsApp / Meta ----
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = (
    os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip()
    or os.getenv("WHATSAPP_WABA_ID", "").strip()
)
WHATSAPP_RECIPIENTS = _csv("WHATSAPP_RECIPIENTS")
# Approved Meta language code (use en_US when that is what Meta approved).
WHATSAPP_TEMPLATE_LANGUAGE = (
    os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en_US").strip() or "en_US"
)
# Single active template while others await approval. Set FORCE_SINGLE=false later
# to restore per-type template names (ARTICLE_ALERT, DAILY, …).
WHATSAPP_TEMPLATE_NAME = (
    os.getenv("WHATSAPP_TEMPLATE_NAME", "").strip() or "mediasphere_critical_issue"
)
WHATSAPP_FORCE_SINGLE_TEMPLATE = _truthy("WHATSAPP_FORCE_SINGLE_TEMPLATE", "true")

# Prefer META_API_VERSION; fall back to existing WhatsApp Graph version.
META_API_VERSION = (
    os.getenv("META_API_VERSION", "").strip()
    or os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0").strip()
    or "v25.0"
)

WHATSAPP_TEMPLATE_ARTICLE_ALERT = (
    os.getenv("WHATSAPP_TEMPLATE_ARTICLE_ALERT", "").strip()
    or os.getenv("WHATSAPP_TEMPLATE_ARTICLE", "").strip()
    or "mediasphere_article_alert"
)
WHATSAPP_TEMPLATE_CRITICAL = os.getenv(
    "WHATSAPP_TEMPLATE_CRITICAL", "mediasphere_critical_issue"
).strip()
WHATSAPP_TEMPLATE_DAILY = os.getenv(
    "WHATSAPP_TEMPLATE_DAILY", "mediasphere_daily_summary"
).strip()
WHATSAPP_TEMPLATE_PIPELINE = os.getenv(
    "WHATSAPP_TEMPLATE_PIPELINE", "mediasphere_pipeline_status"
).strip()
WHATSAPP_TEMPLATE_FAILURE = os.getenv(
    "WHATSAPP_TEMPLATE_FAILURE", "mediasphere_failure_alert"
).strip()
WHATSAPP_TEMPLATE_SYSTEM = os.getenv(
    "WHATSAPP_TEMPLATE_SYSTEM", "mediasphere_system_status"
).strip()

# ---- Queue / retry ----
NOTIFICATION_QUEUE_WORKERS = max(1, _int_env("NOTIFICATION_QUEUE_WORKERS", 2))
NOTIFICATION_MAX_RETRIES = max(1, _int_env("NOTIFICATION_MAX_RETRIES", 4))
NOTIFICATION_RETRY_BASE_SECONDS = max(0.5, float(os.getenv("NOTIFICATION_RETRY_BASE_SECONDS", "1")))

# ---- Misc ----
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "").strip()
NOTIFICATION_TIMEZONE = os.getenv("NOTIFICATION_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"
_commit = (os.getenv("RENDER_GIT_COMMIT") or os.getenv("APP_VERSION") or "dev").strip()
APP_VERSION = os.getenv("APP_VERSION", _commit[:12] or "dev").strip() or "dev"
APP_ENVIRONMENT = (
    os.getenv("APP_ENVIRONMENT", "").strip()
    or ("production" if os.getenv("RENDER") else "development")
)


@lru_cache(maxsize=1)
def email_recipients() -> tuple[str, ...]:
    """Lazy load report recipients to avoid circular imports at module import."""
    try:
        from reports import config as report_config

        return tuple(report_config.REPORT_RECIPIENTS or [])
    except Exception:  # noqa: BLE001
        return tuple(_csv("REPORT_RECIPIENTS"))
