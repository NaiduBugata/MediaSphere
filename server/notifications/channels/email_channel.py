"""Email notification channel — wraps existing reports.email_service behaviour."""

from __future__ import annotations

import time
from pathlib import Path

from notifications import config
from notifications.base import NotificationChannel
from notifications.logger import get_logger, log_delivery
from notifications.models import ChannelResult, NotificationPayload
from notifications import status_store

logger = get_logger("notifications.email")


def _record(result: ChannelResult, *, notification_type: str | None = None) -> ChannelResult:
    if result.skipped:
        status = "skipped"
    elif result.success:
        status = "ok"
    else:
        status = "failed"
    status_store.record(
        "email",
        status=status,
        enabled=True,
        error=result.error or result.skip_reason,
        notification_type=notification_type,
        http_code=result.http_code,
    )
    return result


class EmailChannel(NotificationChannel):
    """Adapter over MediaSphere's existing SMTP/Resend email stack."""

    @property
    def name(self) -> str:
        return "email"

    def is_enabled(self) -> bool:
        # Mirror reports.config.EMAIL_ENABLED so behaviour stays identical.
        try:
            from reports import config as report_config

            return bool(report_config.EMAIL_ENABLED)
        except Exception:  # noqa: BLE001
            return bool(config.EMAIL_ENABLED)

    def send(self, payload: NotificationPayload) -> ChannelResult:
        ntype = payload.notification_type.value
        if not self.is_enabled():
            status_store.record(
                "email",
                status="skipped",
                enabled=False,
                error="email_disabled",
                notification_type=ntype,
            )
            return ChannelResult(
                channel=self.name,
                success=True,
                skipped=True,
                skip_reason="email_disabled",
            )

        if payload.email_incremental:
            return _record(self._send_incremental(payload), notification_type=ntype)

        if not payload.html_body and not payload.subject:
            return _record(
                ChannelResult(
                    channel=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="no_email_content",
                ),
                notification_type=ntype,
            )

        return _record(self._send_report(payload), notification_type=ntype)

    def _send_incremental(self, payload: NotificationPayload) -> ChannelResult:
        from reports import incremental

        started = time.perf_counter()
        try:
            result = incremental.send_incremental_report(
                recipients=payload.recipients_email or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Incremental email channel failed: %s", exc)
            return ChannelResult(channel=self.name, success=False, error=str(exc))

        latency = (time.perf_counter() - started) * 1000
        status = result.get("status") or "unknown"
        success = status in ("sent", "partial", "skipped")
        log_delivery(
            channel=self.name,
            recipient=",".join(result.get("recipients") or []),
            template="incremental_article",
            message_id=result.get("batch_id"),
            latency_ms=latency,
            http_code=None,
            retries=0,
            status=status,
            notification_type=payload.notification_type.value,
            extra={"sent": result.get("sent"), "failed": result.get("failed")},
        )
        return ChannelResult(
            channel=self.name,
            success=success,
            attempts=1,
            message_id=result.get("batch_id"),
            error=result.get("error") if not success else None,
            latency_ms=latency,
            skipped=status == "skipped",
            skip_reason=result.get("reason") if status == "skipped" else None,
        )

    def _send_report(self, payload: NotificationPayload) -> ChannelResult:
        from reports import email_service

        started = time.perf_counter()
        html = payload.html_body or f"<pre>{payload.text_body}</pre>"
        pdf: Path | None = payload.pdf_path
        recipients = payload.recipients_email or None

        try:
            success, attempts, error = email_service.send_report(
                subject=payload.subject or "MediaSphere Notification",
                html_body=html,
                pdf_path=pdf,
                recipients=recipients,
            )
        except email_service.EmailConfigError as exc:
            return ChannelResult(channel=self.name, success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.error("Email send failed: %s", exc)
            return ChannelResult(channel=self.name, success=False, error=str(exc))

        latency = (time.perf_counter() - started) * 1000
        log_delivery(
            channel=self.name,
            recipient=",".join(recipients or config.email_recipients()),
            template=payload.template_name or payload.notification_type.value,
            message_id=None,
            latency_ms=latency,
            http_code=None,
            retries=max(0, attempts - 1),
            status="sent" if success else "failed",
            notification_type=payload.notification_type.value,
        )
        return ChannelResult(
            channel=self.name,
            success=bool(success),
            attempts=attempts,
            error=error,
            latency_ms=latency,
        )
