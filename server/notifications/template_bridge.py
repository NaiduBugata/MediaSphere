"""Map any notification into the 5-variable critical_issue Meta template shape.

Temporary bridge while only ``mediasphere_critical_issue`` is approved.
Disable via ``WHATSAPP_FORCE_SINGLE_TEMPLATE=false`` once other templates are live.
"""

from __future__ import annotations

from typing import Any

from notifications import config
from notifications.formatter import format_datetime, truncate
from notifications.models import NotificationPayload, NotificationType
from notifications.utils import location_label, safe_str

_DEFAULT_LOCATION = "Narasaraopet"


def active_template_name() -> str:
    """Template used for outbound WhatsApp when templates are enabled."""
    if config.WHATSAPP_FORCE_SINGLE_TEMPLATE:
        return (
            config.WHATSAPP_TEMPLATE_NAME
            or config.WHATSAPP_TEMPLATE_CRITICAL
            or "mediasphere_critical_issue"
        )
    return config.WHATSAPP_TEMPLATE_NAME or config.WHATSAPP_TEMPLATE_CRITICAL


def active_template_language() -> str:
    return config.WHATSAPP_TEMPLATE_LANGUAGE or "en_US"


def priority_for_type(notification_type: NotificationType) -> str:
    if notification_type in (NotificationType.CRITICAL_ISSUE, NotificationType.FAILURE):
        return "HIGH"
    if notification_type == NotificationType.HEALTH:
        return "INFO"
    return "INFO"


def vars_from_article(article: dict[str, Any], *, critical: bool = False) -> list[str]:
    """Build {{1}}..{{5}} for an article alert via the critical template."""
    title = truncate(safe_str(article.get("title"), "Untitled"), 120)
    summary = truncate(safe_str(article.get("summary") or article.get("problem")), 180)
    if critical:
        problem = summary or title
        priority = safe_str(article.get("severity"), "HIGH").upper() or "HIGH"
    else:
        problem = f"New article: {title}" + (f" — {summary}" if summary else "")
        problem = truncate(problem, 200)
        priority = "INFO"
    source = safe_str(article.get("source"), "MediaSphere").capitalize() or "MediaSphere"
    return [
        location_label(article) or _DEFAULT_LOCATION,
        problem or "New article collected successfully.",
        priority,
        source,
        format_datetime(None),
    ]


def vars_from_payload(payload: NotificationPayload) -> list[str]:
    """Build {{1}}..{{5}} for any non-article notification payload."""
    meta = payload.metadata or {}
    location = safe_str(meta.get("location"), _DEFAULT_LOCATION)
    message = truncate(
        safe_str(payload.text_body) or safe_str(payload.subject) or "MediaSphere notification",
        200,
    )
    # Prefer a one-line summary over multi-line emoji bodies when possible
    first_line = next((ln.strip() for ln in message.splitlines() if ln.strip()), message)
    if len(first_line) < 20 and message:
        # keep a bit more context
        compact = " ".join(message.split())
        message = truncate(compact, 200)
    else:
        message = truncate(first_line, 200)

    priority = safe_str(meta.get("priority")) or priority_for_type(payload.notification_type)
    source = safe_str(meta.get("source"), "MediaSphere") or "MediaSphere"
    return [
        location,
        message or "MediaSphere notification",
        priority.upper(),
        source,
        format_datetime(None),
    ]


def apply_single_template(payload: NotificationPayload) -> NotificationPayload:
    """Overwrite template name/language/variables for single-template mode."""
    if not config.WHATSAPP_FORCE_SINGLE_TEMPLATE:
        return payload
    variables = list(payload.template_variables or [])
    # Always rebuild to the 5-slot critical shape when forcing single template
    if payload.metadata.get("article"):
        variables = vars_from_article(
            payload.metadata["article"],
            critical=payload.notification_type == NotificationType.CRITICAL_ISSUE,
        )
    else:
        variables = vars_from_payload(payload)
    # Ensure exactly 5 string params
    while len(variables) < 5:
        variables.append("N/A")
    variables = [truncate(safe_str(v, "N/A"), 1024) for v in variables[:5]]
    payload.template_name = active_template_name()
    payload.template_language = active_template_language()
    payload.template_variables = variables
    return payload
