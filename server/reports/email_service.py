"""SMTP email delivery with automatic retry.

Sends the HTML report with the PDF attachment via SMTP (Gmail app password
by default). Credentials are read from config/env; never hardcoded. Failures
are retried with backoff and never raise past the caller in a way that could
crash the scheduler.
"""

from __future__ import annotations

import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from pathlib import Path

from . import config
from .logger import get_logger

logger = get_logger("reports.email")


class EmailConfigError(RuntimeError):
    """Raised when SMTP configuration or recipients are missing."""


def _validate() -> None:
    missing = []
    if not config.SMTP_HOST:
        missing.append("SMTP_HOST")
    if not config.SMTP_USERNAME:
        missing.append("SMTP_USERNAME")
    if not config.SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if not config.REPORT_RECIPIENTS:
        missing.append("REPORT_RECIPIENTS")
    if missing:
        raise EmailConfigError(f"Missing email configuration: {', '.join(missing)}")


def _build_message(subject: str, html_body: str, recipients: list[str], pdf_path: Path | None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_FROM_EMAIL or config.SMTP_USERNAME))
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)

    msg.set_content(
        "This report is best viewed in an HTML-capable email client. "
        "Please see the attached PDF for the full Daily Constituency Intelligence Report."
    )
    msg.add_alternative(html_body, subtype="html")

    if pdf_path and Path(pdf_path).exists():
        data = Path(pdf_path).read_bytes()
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=Path(pdf_path).name)

    return msg


def _send_once(msg: EmailMessage, recipients: list[str]) -> None:
    if config.SMTP_USE_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=60) as server:
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=60) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg, to_addrs=recipients)


def send_report(
    subject: str,
    html_body: str,
    pdf_path: Path | None = None,
    recipients: list[str] | None = None,
) -> tuple[bool, int, str | None]:
    """Send the report email with retry.

    Returns (success, attempts_used, error_message).
    """
    if not config.EMAIL_ENABLED:
        logger.info("Email delivery disabled (EMAIL_ENABLED=false); skipping send.")
        return True, 0, None

    _validate()
    to = recipients or config.REPORT_RECIPIENTS
    msg = _build_message(subject, html_body, to, pdf_path)

    attempts = 0
    last_error: str | None = None
    max_retries = max(1, config.SMTP_MAX_RETRIES)

    while attempts < max_retries:
        attempts += 1
        try:
            _send_once(msg, to)
            logger.info("Report email sent to %s (attempt %d).", ", ".join(to), attempts)
            return True, attempts, None
        except Exception as exc:  # noqa: BLE001 - retry on any SMTP failure
            last_error = str(exc)
            logger.warning("Email send attempt %d/%d failed: %s", attempts, max_retries, exc)
            if attempts < max_retries:
                time.sleep(config.SMTP_RETRY_BACKOFF_SECONDS * attempts)

    logger.error("Email delivery failed after %d attempts: %s", attempts, last_error)
    return False, attempts, last_error
