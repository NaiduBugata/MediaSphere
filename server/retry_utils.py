"""Legacy shim — re-exports from pipeline.retry for backward compatibility."""
# ruff: noqa: F401

import time  # noqa: F401 — tests patch retry_utils.time.sleep

from pipeline.retry import (  # noqa: F401
    TRANSIENT_EXCEPTIONS,
    DEFAULT_RETRIES,
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_MAX_DELAY_SECONDS,
    is_transient,
    retry_call,
)
