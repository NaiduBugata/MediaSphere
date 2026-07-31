"""Notification framework exceptions."""

from __future__ import annotations


class NotificationError(Exception):
    """Base error for the notification framework."""


class ChannelDisabled(NotificationError):
    """Raised when a channel is disabled or misconfigured."""


class RetryableChannelError(NotificationError):
    """Transient channel failure eligible for exponential backoff retry."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
