"""Email delivery with automatic retry.

Supports two transports:
- **smtp** — Gmail app password (works locally / on VPS; blocked on Render free tier)
- **resend** — HTTPS API (works on Render free tier)

Set EMAIL_PROVIDER=resend and RESEND_API_KEY on Render. Keep smtp for local dev.
"""

from __future__ import annotations

import base64
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from pathlib import Path

import requests

from . import config
from .logger import get_logger

logger = get_logger("reports.email")

RESEND_API_URL = "https://api.resend.com/emails"


class EmailConfigError(RuntimeError):
    """Raised when email configuration is missing or invalid."""


def resolve_provider() -> str:
    """Return the active email provider name ('smtp' or 'resend')."""
    if config.EMAIL_PROVIDER == "resend":
        return "resend"
    if config.EMAIL_PROVIDER == "smtp":
        return "smtp"
    # auto: prefer Resend when an API key is present (typical on Render).
    if config.RESEND_API_KEY:
        return "resend"
    return "smtp"


def _validate_smtp() -> None:
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
        raise EmailConfigError(f"Missing SMTP configuration: {', '.join(missing)}")


def _validate_resend() -> None:
    missing = []
    if not config.RESEND_API_KEY:
        missing.append("RESEND_API_KEY")
    if not config.REPORT_RECIPIENTS:
        missing.append("REPORT_RECIPIENTS")
    from_email = config.SMTP_FROM_EMAIL or config.SMTP_USERNAME
    if not from_email:
        missing.append("SMTP_FROM_EMAIL (required as Resend 'from' address)")
    if missing:
        raise EmailConfigError(f"Missing Resend configuration: {', '.join(missing)}")


def _smtp_password() -> str:
    """Gmail app passwords are 16 chars; strip spaces if pasted with gaps."""
    return config.SMTP_PASSWORD.replace(" ", "")


def _build_smtp_message(
    subject: str, html_body: str, recipients: list[str], pdf_path: Path | None
) -> EmailMessage:
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


def _send_smtp_once(msg: EmailMessage, recipients: list[str]) -> None:
    if config.SMTP_USE_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=60) as server:
            server.login(config.SMTP_USERNAME, _smtp_password())
            server.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=60) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.login(config.SMTP_USERNAME, _smtp_password())
            server.send_message(msg, to_addrs=recipients)


def _send_resend_once(
    subject: str,
    html_body: str,
    recipients: list[str],
    pdf_path: Path | None,
) -> None:
    from_email = config.SMTP_FROM_EMAIL or config.SMTP_USERNAME
    from_header = f"{config.SMTP_FROM_NAME} <{from_email}>"

    payload: dict = {
        "from": from_header,
        "to": recipients,
        "subject": subject,
        "html": html_body,
    }

    if pdf_path and Path(pdf_path).exists():
        pdf_bytes = Path(pdf_path).read_bytes()
        payload["attachments"] = [
            {
                "filename": Path(pdf_path).name,
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ]

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {config.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend API {response.status_code}: {response.text[:500]}")


def send_report(
    subject: str,
    html_body: str,
    pdf_path: Path | None = None,
    recipients: list[str] | None = None,
) -> tuple[bool, int, str | None]:
    """Send the report email with retry. Returns (success, attempts, error_message)."""
    if not config.EMAIL_ENABLED:
        logger.info("Email delivery disabled (EMAIL_ENABLED=false); skipping send.")
        return False, 0, "EMAIL_ENABLED=false"

    provider = resolve_provider()
    to = recipients or config.REPORT_RECIPIENTS

    if provider == "resend":
        _validate_resend()
    else:
        _validate_smtp()

    logger.info("Sending email via %s to %s", provider, ", ".join(to))

    attempts = 0
    last_error: str | None = None
    max_retries = max(1, config.SMTP_MAX_RETRIES)
    smtp_msg = (
        _build_smtp_message(subject, html_body, to, pdf_path) if provider == "smtp" else None
    )

    while attempts < max_retries:
        attempts += 1
        try:
            if provider == "resend":
                _send_resend_once(subject, html_body, to, pdf_path)
            else:
                _send_smtp_once(smtp_msg, to)
            logger.info("Report email sent via %s (attempt %d).", provider, attempts)
            return True, attempts, None
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            logger.warning(
                "Email send attempt %d/%d failed (%s): %s",
                attempts,
                max_retries,
                provider,
                exc,
            )
            if attempts < max_retries:
                time.sleep(config.SMTP_RETRY_BACKOFF_SECONDS * attempts)

    logger.error("Email delivery failed after %d attempts (%s): %s", attempts, provider, last_error)
    return False, attempts, last_error


def diagnose() -> dict:
    """Run connectivity checks and return a diagnostic summary (no email sent)."""
    import socket

    result = {
        "email_enabled": config.EMAIL_ENABLED,
        "provider": resolve_provider(),
        "recipients": config.REPORT_RECIPIENTS,
        "smtp_host": config.SMTP_HOST,
        "smtp_port": config.SMTP_PORT,
        "smtp_username_set": bool(config.SMTP_USERNAME),
        "smtp_password_set": bool(config.SMTP_PASSWORD),
        "resend_api_key_set": bool(config.RESEND_API_KEY),
        "smtp_port_465_reachable": None,
        "smtp_port_587_reachable": None,
        "smtp_login_ok": None,
        "resend_api_ok": None,
        "notes": [],
    }

    if not config.EMAIL_ENABLED:
        result["notes"].append("EMAIL_ENABLED=false — no emails will be sent until set to true.")

    provider = resolve_provider()
    if provider == "smtp":
        result["notes"].append(
            "Using SMTP. Render FREE tier blocks ports 465/587/25 → use EMAIL_PROVIDER=resend on Render."
        )
        for port in (465, 587):
            try:
                s = socket.create_connection((config.SMTP_HOST, port), timeout=8)
                s.close()
                result[f"smtp_port_{port}_reachable"] = True
            except OSError as exc:
                result[f"smtp_port_{port}_reachable"] = False
                result["notes"].append(f"Port {port} unreachable: {exc} (expected on Render free tier).")

        if config.SMTP_USERNAME and config.SMTP_PASSWORD:
            try:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(config.SMTP_HOST, 465, context=ctx, timeout=15) as srv:
                    srv.login(config.SMTP_USERNAME, _smtp_password())
                result["smtp_login_ok"] = True
            except Exception as exc:
                result["smtp_login_ok"] = False
                result["notes"].append(f"SMTP login failed: {exc}")
    else:
        result["notes"].append("Using Resend HTTPS API (works on Render free tier).")
        if config.RESEND_API_KEY:
            try:
                resp = requests.get(
                    "https://api.resend.com/domains",
                    headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                    timeout=15,
                )
                result["resend_api_ok"] = resp.status_code < 400
                if resp.status_code >= 400:
                    result["notes"].append(f"Resend API check failed: {resp.status_code} {resp.text[:200]}")
            except Exception as exc:
                result["resend_api_ok"] = False
                result["notes"].append(f"Resend API unreachable: {exc}")

    return result
