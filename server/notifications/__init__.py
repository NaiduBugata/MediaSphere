"""MediaSphere multi-channel notification framework.

Pipeline and schedulers must call :func:`get_notification_manager` only.
Channels (Email, WhatsApp, …) are registered behind the manager.
"""

from __future__ import annotations

from notifications.manager import NotificationManager, get_notification_manager

__all__ = ["NotificationManager", "get_notification_manager"]
