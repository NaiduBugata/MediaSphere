"""Legacy shim — re-exports from sources.lokal constants and config."""
# ruff: noqa: F401

from sources.lokal.config import CHECK_INTERVAL, PIPELINE_INTERVAL_HOURS
from sources.lokal.constants import (
    BACKOFF_FACTOR,
    BASE_URL,
    COLLECTOR_NAME,
    LOOKBACK_HOURS,
    MAX_RETRIES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILENAME,
    PAGE_SIZE,
    POST_TYPES,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_STATUS_CODES,
    SOURCE_URL,
    TAG_ID,
    USER_AGENT,
    WEBSITE_BASE_URL,
)
