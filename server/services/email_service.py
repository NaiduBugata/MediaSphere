"""Email service facade — delegates to reports.email_service."""

from __future__ import annotations

from reports.email_service import send_report  # noqa: F401


def send_notification_email(
    subject: str,
    html_body: str,
    recipients: list[str] | None = None,
) -> dict:
    """Send an email notification using the configured provider."""
    from reports import config as report_config

    to = recipients or report_config.REPORT_RECIPIENTS
    if not to:
        return {"status": "skipped", "reason": "no recipients configured"}
    return send_report(subject=subject, html_body=html_body, recipients=to)
