"""WhatsApp Cloud API notification channel."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from notifications import config
from notifications.base import NotificationChannel
from notifications.exceptions import RetryableChannelError
from notifications.logger import get_logger, log_delivery
from notifications.models import ChannelResult, NotificationPayload, NotificationType
from notifications.retry import is_retryable_status, retry_call
from notifications.template_bridge import (
    active_template_language,
    active_template_name,
    apply_single_template,
    vars_from_article,
)
from notifications.templates import article_alert, critical_issue
from notifications.utils import is_critical_article, normalize_phone

logger = get_logger("notifications.whatsapp")

# Meta codes that mean template cannot be used — fall back to text.
_TEMPLATE_ERROR_CODES = frozenset({132000, 132001, 132005, 132007, 132012, 132015, 132016})


class WhatsAppChannel(NotificationChannel):
    """Deliver notifications via Meta WhatsApp Cloud API."""

    @property
    def name(self) -> str:
        return "whatsapp"

    def is_enabled(self) -> bool:
        return bool(
            config.WHATSAPP_ENABLED
            and config.WHATSAPP_ACCESS_TOKEN
            and config.WHATSAPP_PHONE_NUMBER_ID
            and config.WHATSAPP_RECIPIENTS
        )

    def send(self, payload: NotificationPayload) -> ChannelResult:
        if not self.is_enabled():
            return ChannelResult(
                channel=self.name,
                success=True,
                skipped=True,
                skip_reason="whatsapp_disabled_or_misconfigured",
            )

        if payload.whatsapp_pending_articles:
            return self._send_pending_articles(critical_only=payload.critical_only)

        payload = apply_single_template(payload)
        recipients = payload.recipients_whatsapp or list(config.WHATSAPP_RECIPIENTS)
        if not recipients:
            return ChannelResult(
                channel=self.name,
                success=True,
                skipped=True,
                skip_reason="no_recipients",
            )

        last: ChannelResult | None = None
        any_success = False
        last_error: str | None = None
        last_message_id: str | None = None
        for recipient in recipients:
            last = self._send_one(payload, recipient)
            if last.success and not last.skipped:
                any_success = True
                last_message_id = last.message_id or last_message_id
            elif last.error:
                last_error = last.error
        if last is None:
            return ChannelResult(channel=self.name, success=False, error="no_recipients_processed")
        return ChannelResult(
            channel=self.name,
            success=any_success,
            attempts=last.attempts,
            message_id=last_message_id or last.message_id,
            error=None if any_success else (last_error or last.error),
            latency_ms=last.latency_ms,
        )

    def _send_pending_articles(self, *, critical_only: bool) -> ChannelResult:
        """Send WhatsApp alerts for Mongo docs with whatsapp_sent=False."""
        import mongo_store
        from reports import data_service

        collection = mongo_store.get_collection()
        docs = list(collection.find({"whatsapp_sent": False}))
        if not docs:
            return ChannelResult(
                channel=self.name,
                success=True,
                skipped=True,
                skip_reason="no_pending_articles",
            )

        sent = 0
        failed = 0
        for doc in docs:
            article = data_service.enrich(data_service._normalize(doc))
            critical = is_critical_article(article)
            if critical_only and not critical:
                continue

            text = (
                critical_issue.build_text(article)
                if critical
                else article_alert.build_text(article)
            )
            ntype = (
                NotificationType.CRITICAL_ISSUE if critical else NotificationType.ARTICLE_ALERT
            )
            payload = NotificationPayload(
                notification_type=ntype,
                subject=ntype.value,
                text_body=text,
                template_name=active_template_name(),
                template_language=active_template_language(),
                template_variables=vars_from_article(article, critical=critical),
                recipients_whatsapp=list(config.WHATSAPP_RECIPIENTS),
                metadata={"post_id": article.get("post_id"), "critical": critical, "article": article},
            )
            payload = apply_single_template(payload)

            article_ok = False
            message_id = None
            for recipient in config.WHATSAPP_RECIPIENTS:
                result = self._send_one(payload, recipient)
                if result.success and not result.skipped:
                    article_ok = True
                    message_id = result.message_id or message_id

            if article_ok:
                self._mark_whatsapp_sent(article.get("post_id"), message_id, critical=critical)
                sent += 1
            else:
                failed += 1

        return ChannelResult(
            channel=self.name,
            success=failed == 0,
            attempts=sent + failed,
            error=None if failed == 0 else f"{failed}_failed",
            skipped=sent == 0 and failed == 0,
        )

    def _mark_whatsapp_sent(self, post_id: Any, message_id: str | None, *, critical: bool) -> None:
        if not post_id:
            return
        import mongo_store

        now = datetime.now(timezone.utc).isoformat()
        update: dict[str, Any] = {
            "whatsapp_sent": True,
            "whatsapp_sent_at": now,
            "whatsapp_message_id": message_id,
        }
        if critical:
            update["whatsapp_critical_sent"] = True
            update["whatsapp_critical_sent_at"] = now
        mongo_store.get_collection().update_one({"post_id": post_id}, {"$set": update})

    def _is_template_error(self, exc: Exception) -> bool:
        msg = str(exc)
        if "132001" in msg or "Template name does not exist" in msg:
            return True
        if "132000" in msg or "template" in msg.lower() and "error" in msg.lower():
            code = getattr(exc, "status_code", None)
            if code in (400, 404):
                return True
        meta_code = getattr(exc, "meta_error_code", None)
        return meta_code in _TEMPLATE_ERROR_CODES

    def _send_one(self, payload: NotificationPayload, recipient: str) -> ChannelResult:
        from whatsapp.send_service import WhatsAppSendError, send_template_message, send_text_message

        try:
            to = normalize_phone(recipient)
        except ValueError as exc:
            return ChannelResult(channel=self.name, success=False, error=str(exc))

        started = time.perf_counter()
        template_name = payload.template_name or active_template_name()
        language = payload.template_language or active_template_language()
        variables = list(payload.template_variables or [])

        def _attempt_template() -> dict[str, Any]:
            try:
                return send_template_message(
                    to,
                    template_name,
                    language=language,
                    body_parameters=variables or None,
                )
            except WhatsAppSendError as exc:
                status = getattr(exc, "status_code", None)
                if status is None:
                    for code in (429, 500, 502, 503, 504):
                        if f" {code}:" in str(exc) or f"error {code}:" in str(exc):
                            status = code
                            break
                if is_retryable_status(status) or "timed out" in str(exc).lower():
                    raise RetryableChannelError(str(exc), status_code=status) from exc
                raise

        def _attempt_text() -> dict[str, Any]:
            try:
                return send_text_message(to, payload.text_body)
            except WhatsAppSendError as exc:
                status = getattr(exc, "status_code", None)
                if is_retryable_status(status) or "timed out" in str(exc).lower():
                    raise RetryableChannelError(str(exc), status_code=status) from exc
                raise

        use_templates = config.WHATSAPP_USE_TEMPLATES
        try:
            if use_templates:
                logger.info(
                    "WhatsApp template send | template=%s | language=%s | recipient=%s | vars=%s",
                    template_name,
                    language,
                    to,
                    variables,
                )
                data, attempts = retry_call(
                    _attempt_template,
                    label=f"whatsapp:{payload.notification_type.value}",
                )
            else:
                data, attempts = retry_call(
                    _attempt_text,
                    label=f"whatsapp_text:{payload.notification_type.value}",
                )

            latency = (time.perf_counter() - started) * 1000
            message_id = None
            messages = data.get("messages") if isinstance(data, dict) else None
            if isinstance(messages, list) and messages:
                message_id = messages[0].get("id")
            log_delivery(
                channel=self.name,
                recipient=to,
                template=template_name if use_templates else None,
                message_id=message_id,
                latency_ms=latency,
                http_code=200,
                retries=max(0, attempts - 1),
                status="sent",
                notification_type=payload.notification_type.value,
                extra={
                    "language": language if use_templates else None,
                    "variables": variables if use_templates else None,
                    "meta_response": data,
                },
            )
            return ChannelResult(
                channel=self.name,
                success=True,
                attempts=attempts,
                message_id=message_id,
                http_code=200,
                latency_ms=latency,
            )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - started) * 1000
            logger.error(
                "WhatsApp template/send failed | template=%s | language=%s | recipient=%s | "
                "vars=%s | error=%s",
                template_name,
                language,
                to,
                variables,
                exc,
            )

            # Fallback to plain text when template is unavailable (do not crash).
            if use_templates and self._is_template_error(exc):
                logger.warning(
                    "Falling back to plain text for %s after template error: %s", to, exc
                )
                try:
                    data, attempts = retry_call(
                        _attempt_text,
                        label=f"whatsapp_fallback:{payload.notification_type.value}",
                    )
                    message_id = None
                    messages = data.get("messages") if isinstance(data, dict) else None
                    if isinstance(messages, list) and messages:
                        message_id = messages[0].get("id")
                    latency = (time.perf_counter() - started) * 1000
                    log_delivery(
                        channel=self.name,
                        recipient=to,
                        template=template_name,
                        message_id=message_id,
                        latency_ms=latency,
                        http_code=200,
                        retries=max(0, attempts - 1),
                        status="sent_text_fallback",
                        notification_type=payload.notification_type.value,
                        extra={
                            "language": language,
                            "variables": variables,
                            "template_error": str(exc),
                            "meta_response": data,
                        },
                    )
                    return ChannelResult(
                        channel=self.name,
                        success=True,
                        attempts=attempts,
                        message_id=message_id,
                        http_code=200,
                        latency_ms=latency,
                    )
                except Exception as fallback_exc:  # noqa: BLE001
                    logger.error("WhatsApp text fallback also failed for %s: %s", to, fallback_exc)
                    exc = fallback_exc

            log_delivery(
                channel=self.name,
                recipient=to,
                template=template_name,
                message_id=None,
                latency_ms=latency,
                http_code=getattr(exc, "status_code", None),
                retries=config.NOTIFICATION_MAX_RETRIES,
                status="failed",
                notification_type=payload.notification_type.value,
                extra={
                    "language": language,
                    "variables": variables,
                    "error": str(exc),
                },
            )
            return ChannelResult(
                channel=self.name,
                success=False,
                attempts=config.NOTIFICATION_MAX_RETRIES,
                error=str(exc),
                latency_ms=latency,
            )
