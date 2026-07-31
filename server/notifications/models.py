"""Notification domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class NotificationType(str, Enum):
    ARTICLE_ALERT = "article_alert"
    CRITICAL_ISSUE = "critical_issue"
    DAILY_SUMMARY = "daily_summary"
    PIPELINE_COMPLETE = "pipeline_complete"
    FAILURE = "failure"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    HEALTH = "health"
    CUSTOM = "custom"


@dataclass
class ChannelResult:
    """Outcome of sending through one channel."""

    channel: str
    success: bool
    attempts: int = 0
    message_id: str | None = None
    error: str | None = None
    http_code: int | None = None
    latency_ms: float | None = None
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class NotificationPayload:
    """Normalized payload passed to every channel."""

    notification_type: NotificationType
    subject: str
    text_body: str
    html_body: str | None = None
    pdf_path: Path | None = None
    recipients_email: list[str] = field(default_factory=list)
    recipients_whatsapp: list[str] = field(default_factory=list)
    template_name: str | None = None
    template_language: str | None = None
    template_variables: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # When True, EmailChannel runs the incremental pending-article loop.
    email_incremental: bool = False
    # When True, WhatsAppChannel sends pending article/critical alerts from Mongo.
    whatsapp_pending_articles: bool = False
    critical_only: bool = False


@dataclass
class NotificationJob:
    """Queued work item for the async dispatcher."""

    payload: NotificationPayload
    channels: list[str] | None = None  # None = all enabled
