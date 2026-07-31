"""Exponential backoff retry for notification channels."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from notifications import config
from notifications.exceptions import RetryableChannelError
from notifications.logger import get_logger

logger = get_logger("notifications.retry")

T = TypeVar("T")

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def is_retryable_status(status_code: int | None) -> bool:
    return status_code is not None and status_code in RETRYABLE_STATUS_CODES


def retry_call(
    func: Callable[[], T],
    *,
    label: str = "notification",
    max_retries: int | None = None,
    base_seconds: float | None = None,
) -> tuple[T, int]:
    """
    Call ``func`` with exponential backoff on :class:`RetryableChannelError`.

    Returns:
        Tuple of (result, attempts_used).
    """
    attempts_limit = max_retries if max_retries is not None else config.NOTIFICATION_MAX_RETRIES
    base = base_seconds if base_seconds is not None else config.NOTIFICATION_RETRY_BASE_SECONDS
    last_error: Exception | None = None

    for attempt in range(1, attempts_limit + 1):
        try:
            return func(), attempt
        except RetryableChannelError as exc:
            last_error = exc
            if attempt >= attempts_limit:
                break
            delay = base * (2 ** (attempt - 1))
            logger.warning(
                "%s attempt %s/%s failed (retryable): %s; sleeping %.1fs",
                label,
                attempt,
                attempts_limit,
                exc,
                delay,
            )
            time.sleep(delay)
        except Exception:
            raise

    assert last_error is not None
    raise last_error
