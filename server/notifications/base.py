"""Notification channel abstract base."""

from __future__ import annotations

from abc import ABC, abstractmethod

from notifications.models import ChannelResult, NotificationPayload


class NotificationChannel(ABC):
    """Interface for Email, WhatsApp, and future delivery channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable channel identifier (e.g. ``email``, ``whatsapp``)."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Return True when this channel should receive jobs."""

    @abstractmethod
    def send(self, payload: NotificationPayload) -> ChannelResult:
        """Deliver ``payload``. Must not raise for expected failures — return ChannelResult."""
