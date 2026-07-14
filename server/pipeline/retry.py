"""Shared exponential-backoff retries for transient pipeline failures."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from pymongo.errors import AutoReconnect, ConnectionFailure, NetworkTimeout, ServerSelectionTimeoutError

logger = logging.getLogger("retry_utils")

T = TypeVar("T")

TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
    ServerSelectionTimeoutError,
    AutoReconnect,
    NetworkTimeout,
    ConnectionFailure,
)

DEFAULT_RETRIES = 3
DEFAULT_BASE_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 30.0


def is_transient(exc: BaseException) -> bool:
    """Return True for network / Mongo connectivity failures worth retrying."""
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True
    message = str(exc).lower()
    markers = ("timed out", "timeout", "temporarily unavailable", "connection reset", "503", "502", "429")
    return any(marker in message for marker in markers)


def retry_call(
    fn: Callable[[], T],
    *,
    retries: int = DEFAULT_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    exceptions: tuple[type[BaseException], ...] | None = None,
    label: str = "operation",
) -> T:
    """
    Call ``fn`` with exponential backoff + jitter on transient failures.

    Permanent failures (non-transient) raise immediately. Exhausted retries
    re-raise the last exception.
    """
    last_exc: BaseException | None = None
    attempts = max(1, retries)

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - classified below
            last_exc = exc
            allowed = exceptions or TRANSIENT_EXCEPTIONS
            transient = isinstance(exc, allowed) or is_transient(exc)
            if not transient or attempt >= attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay + random.uniform(0, delay * 0.25)
            logger.warning(
                "%s failed (attempt %s/%s): %s; retrying in %.2fs",
                label,
                attempt,
                attempts,
                exc,
                delay,
            )
            time.sleep(delay)

    assert last_exc is not None
    raise last_exc
