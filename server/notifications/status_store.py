"""Persist last notification delivery outcome per channel (for Settings UI)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

COLLECTION_NAME = "notification_channel_status"

VALID_STATUSES = frozenset({"ok", "failed", "skipped"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_collection():
    import mongo_store

    client = mongo_store.get_client()
    return client[mongo_store.MONGODB_DB_NAME][COLLECTION_NAME]


def record(
    channel: str,
    *,
    status: str,
    enabled: bool = True,
    error: str | None = None,
    notification_type: str | None = None,
    http_code: int | None = None,
) -> None:
    """Upsert last delivery outcome for ``email`` or ``whatsapp``."""
    if channel not in ("email", "whatsapp"):
        return
    normalized = status if status in VALID_STATUSES else ("ok" if status in ("sent", "partial", "sent_text_fallback") else "failed")
    if status == "skipped":
        normalized = "skipped"
    elif status in ("sent", "partial", "sent_text_fallback", "ok"):
        normalized = "ok"
    elif status in ("failed", "error"):
        normalized = "failed"

    try:
        get_collection().update_one(
            {"_id": channel},
            {
                "$set": {
                    "enabled": bool(enabled),
                    "last_status": normalized,
                    "last_error": (error or None) and str(error)[:500],
                    "last_at": _now(),
                    "last_notification_type": notification_type,
                    "http_code": http_code,
                }
            },
            upsert=True,
        )
    except Exception:  # noqa: BLE001 - status store must never break delivery
        pass


def get(channel: str) -> dict[str, Any] | None:
    try:
        doc = get_collection().find_one({"_id": channel})
    except Exception:  # noqa: BLE001
        return None
    if not doc:
        return None
    return {
        "channel": doc.get("_id"),
        "enabled": doc.get("enabled"),
        "last_status": doc.get("last_status"),
        "last_error": doc.get("last_error"),
        "last_at": doc.get("last_at"),
        "last_notification_type": doc.get("last_notification_type"),
        "http_code": doc.get("http_code"),
    }


def get_all() -> dict[str, dict[str, Any] | None]:
    return {"email": get("email"), "whatsapp": get("whatsapp")}


def _email_configured() -> tuple[bool, bool]:
    """Return (enabled, configured) for email — no secrets."""
    try:
        from reports import config as report_config

        enabled = bool(report_config.EMAIL_ENABLED)
        recipients = list(report_config.REPORT_RECIPIENTS or [])
        provider = (getattr(report_config, "EMAIL_PROVIDER", "") or "auto").lower()
        has_resend = bool(getattr(report_config, "RESEND_API_KEY", "") or "")
        has_smtp = bool(
            getattr(report_config, "SMTP_USERNAME", "")
            and getattr(report_config, "SMTP_PASSWORD", "")
        )
        configured = bool(recipients) and (
            has_resend if provider == "resend" else (has_resend or has_smtp)
        )
        if provider == "auto":
            configured = bool(recipients) and (has_resend or has_smtp)
        return enabled, configured
    except Exception:  # noqa: BLE001
        from notifications import config

        return bool(config.EMAIL_ENABLED), bool(config.email_recipients())


def _whatsapp_configured() -> tuple[bool, bool]:
    from notifications import config

    enabled = bool(config.WHATSAPP_ENABLED)
    configured = bool(
        config.WHATSAPP_ACCESS_TOKEN
        and config.WHATSAPP_PHONE_NUMBER_ID
        and config.WHATSAPP_RECIPIENTS
    )
    return enabled, configured


def _pending_counts() -> tuple[int, int]:
    try:
        import mongo_store

        coll = mongo_store.get_collection()
        email_pending = coll.count_documents({"email_sent": False})
        # Missing flag is not "pending" for WhatsApp (avoids blasting old docs)
        wa_pending = coll.count_documents({"whatsapp_sent": False})
        return int(email_pending), int(wa_pending)
    except Exception:  # noqa: BLE001
        return 0, 0


def _last_daily_report() -> dict[str, Any] | None:
    try:
        from reports import db_service

        rows = db_service.history(limit=1)
        if not rows:
            return None
        row = rows[0]
        return {
            "status": row.get("status"),
            "report_date": row.get("report_date"),
            "error": row.get("error"),
            "sent_time": row.get("sent_time"),
        }
    except Exception:  # noqa: BLE001
        return None


def _public_status(
    *,
    enabled: bool,
    configured: bool,
    stored: dict[str, Any] | None,
) -> str:
    if not enabled:
        return "disabled"
    if not configured:
        return "failed"
    if not stored or not stored.get("last_status"):
        return "unknown"
    last = stored.get("last_status")
    if last == "ok":
        return "ok"
    if last == "failed":
        return "failed"
    if last == "skipped":
        # Skipped while enabled usually means nothing to send — treat as ok-ish unknown
        return "ok"
    return "unknown"


def build_status_snapshot() -> dict[str, Any]:
    """Aggregate env + last delivery + pending counts for the Settings UI."""
    email_enabled, email_configured = _email_configured()
    wa_enabled, wa_configured = _whatsapp_configured()
    email_pending, wa_pending = _pending_counts()
    stored = get_all()
    email_stored = stored.get("email")
    wa_stored = stored.get("whatsapp")

    email_status = _public_status(
        enabled=email_enabled, configured=email_configured, stored=email_stored
    )
    # Misconfigured while enabled surfaces as failed with a clear error
    email_error = None
    if email_enabled and not email_configured:
        email_error = "missing_recipients_or_provider_credentials"
    elif email_stored and email_stored.get("last_status") == "failed":
        email_error = email_stored.get("last_error")

    wa_status = _public_status(
        enabled=wa_enabled, configured=wa_configured, stored=wa_stored
    )
    wa_error = None
    if wa_enabled and not wa_configured:
        wa_error = "missing_token_phone_id_or_recipients"
    elif wa_stored and wa_stored.get("last_status") == "failed":
        wa_error = wa_stored.get("last_error")

    return {
        "email": {
            "enabled": email_enabled,
            "configured": email_configured,
            "status": email_status,
            "last_at": (email_stored or {}).get("last_at"),
            "last_error": email_error,
            "pending_articles": email_pending,
            "last_daily_report": _last_daily_report(),
        },
        "whatsapp": {
            "enabled": wa_enabled,
            "configured": wa_configured,
            "status": wa_status,
            "last_at": (wa_stored or {}).get("last_at"),
            "last_error": wa_error,
            "pending_articles": wa_pending,
        },
    }
