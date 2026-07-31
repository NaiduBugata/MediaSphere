"""Central Notification Manager — sole notification interface for MediaSphere."""

from __future__ import annotations

import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from notifications import config
from notifications.base import NotificationChannel
from notifications.channels.email_channel import EmailChannel
from notifications.channels.whatsapp_channel import WhatsAppChannel
from notifications.formatter import format_datetime
from notifications.logger import get_logger
from notifications.models import ChannelResult, NotificationJob, NotificationPayload, NotificationType
from notifications.queue import get_queue
from notifications.templates import (
    article_alert,
    critical_issue,
    daily_summary,
    error_alert,
    pipeline_status,
)
from notifications.utils import is_critical_article

logger = get_logger("notifications.manager")


class NotificationManager:
    """
    Fan-out notifications to registered channels via an async queue.

    Callers must use this class (or :func:`get_notification_manager`) and must
    not invoke Email/WhatsApp transports directly.
    """

    def __init__(self, channels: list[NotificationChannel] | None = None) -> None:
        self._channels: list[NotificationChannel] = channels or [
            EmailChannel(),
            WhatsAppChannel(),
        ]

    def register_channel(self, channel: NotificationChannel) -> None:
        """Register an additional channel (Telegram, Slack, …)."""
        self._channels = [c for c in self._channels if c.name != channel.name] + [channel]

    def enabled_channels(self) -> list[NotificationChannel]:
        return [c for c in self._channels if c.is_enabled()]

    # ---- Public API ----

    def notify_new_article(self, article: dict[str, Any] | None = None, *, async_: bool = True) -> dict[str, Any]:
        """
        Notify about new article(s).

        When ``article`` is omitted, Email + WhatsApp process all pending Mongo
        documents (``email_sent=false`` / ``whatsapp_sent=false``), preserving
        existing incremental email semantics.
        """
        if article is not None:
            text = article_alert.build_text(article)
            from notifications.formatter import article_template_variables

            payload = NotificationPayload(
                notification_type=NotificationType.ARTICLE_ALERT,
                subject="MediaSphere Article Alert",
                text_body=text,
                template_name=config.WHATSAPP_TEMPLATE_ARTICLE_ALERT,
                template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
                template_variables=article_template_variables(article),
                recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
                metadata={"post_id": article.get("post_id")},
                email_incremental=False,
                whatsapp_pending_articles=False,
            )
            # Single-article path: WhatsApp immediate; email still via pending batch preferred.
            return self._dispatch(payload, channels=["whatsapp"], async_=async_)

        payload = NotificationPayload(
            notification_type=NotificationType.ARTICLE_ALERT,
            subject="MediaSphere Article Alerts",
            text_body="Pending article notifications",
            email_incremental=True,
            whatsapp_pending_articles=True,
            critical_only=False,
            recipients_email=list(config.email_recipients()),
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
        )
        result = self._dispatch(payload, async_=async_)

        # Second pass for critical-only louder alerts is handled inside WhatsApp
        # pending loop when critical articles are detected.
        return result

    def notify_critical_issue(self, article: dict[str, Any], *, async_: bool = True) -> dict[str, Any]:
        if not is_critical_article(article):
            return {"status": "skipped", "reason": "not_critical"}
        from notifications.formatter import critical_template_variables

        text = critical_issue.build_text(article)
        payload = NotificationPayload(
            notification_type=NotificationType.CRITICAL_ISSUE,
            subject="MediaSphere Critical Issue",
            text_body=text,
            template_name=config.WHATSAPP_TEMPLATE_CRITICAL,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=critical_template_variables(article),
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
            metadata={"post_id": article.get("post_id")},
        )
        return self._dispatch(payload, channels=["whatsapp"], async_=async_)

    def notify_daily_summary(
        self,
        stats: dict[str, Any],
        *,
        report_date: date | str | None = None,
        subject: str | None = None,
        html_body: str | None = None,
        pdf_path: Path | str | None = None,
        recipients: list[str] | None = None,
        async_: bool = False,
    ) -> dict[str, Any]:
        """Send daily digest. Email uses provided HTML/PDF; WhatsApp uses text summary."""
        if isinstance(report_date, date):
            date_str = report_date.isoformat()
        else:
            date_str = report_date or date.today().isoformat()

        text = daily_summary.build_text(stats or {}, report_date=date_str)
        pdf = Path(pdf_path) if pdf_path else None
        payload = NotificationPayload(
            notification_type=NotificationType.DAILY_SUMMARY,
            subject=subject or f"MediaSphere Daily Constituency Report - {date_str}",
            text_body=text,
            html_body=html_body,
            pdf_path=pdf,
            recipients_email=recipients or list(config.email_recipients()),
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
            template_name=config.WHATSAPP_TEMPLATE_DAILY,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=[
                date_str,
                str(stats.get("total") or stats.get("article_count") or 0),
                str(stats.get("positive_count") or 0),
                str(stats.get("negative_count") or 0),
                str(stats.get("problem_count") or stats.get("high_priority_problems") or 0),
                config.DASHBOARD_URL or "N/A",
            ],
        )
        return self._dispatch(payload, async_=async_)

    def notify_pipeline_complete(self, stats: dict[str, Any], *, async_: bool = True) -> dict[str, Any]:
        text = pipeline_status.build_text(stats or {})
        payload = NotificationPayload(
            notification_type=NotificationType.PIPELINE_COMPLETE,
            subject="MediaSphere Pipeline Completed",
            text_body=text,
            html_body=f"<pre>{text}</pre>",
            recipients_email=list(config.email_recipients()),
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
            template_name=config.WHATSAPP_TEMPLATE_PIPELINE,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=[
                str(stats.get("inserted", 0)),
                str(stats.get("articles_fetched", stats.get("fetched", 0))),
                str(stats.get("duration_seconds", "—")),
                str(stats.get("status", "ok")),
            ],
        )
        # Pipeline status: WhatsApp by default; email optional via same payload if enabled
        return self._dispatch(payload, channels=["whatsapp"], async_=async_)

    def notify_failure(
        self,
        *,
        module: str,
        reason: str,
        retry_status: str = "N/A",
        async_: bool = True,
    ) -> dict[str, Any]:
        text = error_alert.build_text(module=module, reason=reason, retry_status=retry_status)
        payload = NotificationPayload(
            notification_type=NotificationType.FAILURE,
            subject=f"MediaSphere Failure — {module}",
            text_body=text,
            html_body=f"<pre>{text}</pre>",
            recipients_email=list(config.email_recipients()),
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
            template_name=config.WHATSAPP_TEMPLATE_FAILURE,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=[module, reason[:200], format_datetime(None)],
        )
        return self._dispatch(payload, async_=async_)

    def notify_startup(self, details: dict[str, str] | None = None, *, async_: bool = True) -> dict[str, Any]:
        text = error_alert.build_startup_text(
            environment=config.APP_ENVIRONMENT,
            version=config.APP_VERSION,
            details=details
            or {
                "Collectors Loaded": "yes",
                "Scheduler": "configured",
                "Mongo Connected": "warming",
                "Notification Services": "ready",
            },
        )
        payload = NotificationPayload(
            notification_type=NotificationType.STARTUP,
            subject="MediaSphere Started",
            text_body=text,
            template_name=config.WHATSAPP_TEMPLATE_SYSTEM,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=[
                "STARTED",
                config.APP_ENVIRONMENT,
                config.APP_VERSION,
                format_datetime(None),
            ],
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
        )
        return self._dispatch(payload, channels=["whatsapp"], async_=async_)

    def notify_shutdown(self, *, async_: bool = False) -> dict[str, Any]:
        text = error_alert.build_shutdown_text(
            environment=config.APP_ENVIRONMENT,
            version=config.APP_VERSION,
        )
        payload = NotificationPayload(
            notification_type=NotificationType.SHUTDOWN,
            subject="MediaSphere Shutdown",
            text_body=text,
            template_name=config.WHATSAPP_TEMPLATE_SYSTEM,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=[
                "SHUTDOWN",
                config.APP_ENVIRONMENT,
                config.APP_VERSION,
                format_datetime(None),
            ],
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
        )
        return self._dispatch(payload, channels=["whatsapp"], async_=async_)

    def notify_health(self, checks: dict[str, str] | None = None, *, async_: bool = True) -> dict[str, Any]:
        text = error_alert.build_health_text(
            checks
            or {
                "Database": "ok",
                "Collectors": "ok",
                "Email": "ok" if config.EMAIL_ENABLED else "disabled",
                "WhatsApp": "ok" if config.WHATSAPP_ENABLED else "disabled",
                "Scheduler": "ok",
            }
        )
        payload = NotificationPayload(
            notification_type=NotificationType.HEALTH,
            subject="MediaSphere Health Report",
            text_body=text,
            template_name=config.WHATSAPP_TEMPLATE_SYSTEM,
            template_language=config.WHATSAPP_TEMPLATE_LANGUAGE,
            template_variables=["HEALTH", config.APP_ENVIRONMENT, config.APP_VERSION, format_datetime(None)],
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
            recipients_email=list(config.email_recipients()),
            html_body=f"<pre>{text}</pre>",
        )
        return self._dispatch(payload, async_=async_)

    def notify_custom(
        self,
        *,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        channels: list[str] | None = None,
        async_: bool = True,
    ) -> dict[str, Any]:
        payload = NotificationPayload(
            notification_type=NotificationType.CUSTOM,
            subject=subject,
            text_body=text_body,
            html_body=html_body or f"<pre>{text_body}</pre>",
            recipients_email=list(config.email_recipients()),
            recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
        )
        return self._dispatch(payload, channels=channels, async_=async_)

    # ---- Internals ----

    def _dispatch(
        self,
        payload: NotificationPayload,
        *,
        channels: list[str] | None = None,
        async_: bool = True,
    ) -> dict[str, Any]:
        job = NotificationJob(payload=payload, channels=channels)

        def _run() -> dict[str, Any]:
            results: list[ChannelResult] = []
            for channel in self._channels:
                if channels is not None and channel.name not in channels:
                    continue
                force_invoke = (
                    (payload.email_incremental and channel.name == "email")
                    or (
                        payload.notification_type == NotificationType.DAILY_SUMMARY
                        and channel.name == "email"
                    )
                    or (
                        payload.whatsapp_pending_articles and channel.name == "whatsapp"
                    )
                )
                if not channel.is_enabled() and not force_invoke:
                    results.append(
                        ChannelResult(
                            channel=channel.name,
                            success=True,
                            skipped=True,
                            skip_reason="disabled",
                        )
                    )
                    continue
                try:
                    results.append(channel.send(payload))
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Channel %s crashed: %s", channel.name, exc)
                    results.append(
                        ChannelResult(channel=channel.name, success=False, error=str(exc))
                    )
            return {
                "status": "ok",
                "notification_type": payload.notification_type.value,
                "results": [
                    {
                        "channel": r.channel,
                        "success": r.success,
                        "skipped": r.skipped,
                        "error": r.error,
                        "message_id": r.message_id,
                        "skip_reason": r.skip_reason,
                    }
                    for r in results
                ],
                "ts": datetime.utcnow().isoformat(),
            }

        if async_:
            get_queue().submit(_run, job)
            return {
                "status": "queued",
                "notification_type": payload.notification_type.value,
            }
        return _run()


_manager: NotificationManager | None = None
_manager_lock = threading.Lock()


def get_notification_manager() -> NotificationManager:
    """Return the process-wide NotificationManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = NotificationManager()
    return _manager
