"""Async notification queue backed by ThreadPoolExecutor."""

from __future__ import annotations

import atexit
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from notifications import config
from notifications.logger import get_logger
from notifications.models import NotificationJob

logger = get_logger("notifications.queue")


class AsyncNotificationQueue:
    """Fire-and-forget dispatcher so collectors never block on channel I/O."""

    def __init__(self, workers: int | None = None) -> None:
        self._workers = workers or config.NOTIFICATION_QUEUE_WORKERS
        self._executor = ThreadPoolExecutor(
            max_workers=self._workers,
            thread_name_prefix="notif",
        )
        self._lock = threading.Lock()
        self._pending: set[Future[Any]] = set()
        atexit.register(self.shutdown)

    def submit(self, fn: Callable[[], Any], job: NotificationJob | None = None) -> Future[Any]:
        """Schedule ``fn`` on the worker pool. Exceptions are logged, never raised to caller."""

        def _runner() -> Any:
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                kind = job.payload.notification_type.value if job else "unknown"
                logger.exception("Async notification job failed (%s): %s", kind, exc)
                return None

        future = self._executor.submit(_runner)
        with self._lock:
            self._pending.add(future)

        def _done(fut: Future[Any]) -> None:
            with self._lock:
                self._pending.discard(fut)

        future.add_done_callback(_done)
        return future

    def shutdown(self, wait: bool = False) -> None:
        try:
            self._executor.shutdown(wait=wait, cancel_futures=not wait)
        except TypeError:
            # Python < 3.9 cancel_futures unsupported
            self._executor.shutdown(wait=wait)


_queue: AsyncNotificationQueue | None = None
_queue_lock = threading.Lock()


def get_queue() -> AsyncNotificationQueue:
    global _queue
    if _queue is None:
        with _queue_lock:
            if _queue is None:
                _queue = AsyncNotificationQueue()
    return _queue
