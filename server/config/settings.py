"""Runtime settings loaded from environment variables.

Pipeline-specific settings (PIPELINE_ON_API, discover_groq_keys, etc.)
live in pipeline_config.py at server root — this module re-exports them
for convenience.
"""

from __future__ import annotations

from config.environment import _float_env, _int_env, _truthy  # noqa: F401

# ---- Lokal legacy API (orchestrator / lokal_news_collector) ----
API_BASE_URL = "https://lokalnews.in/wp-json/wp/v2/posts"
API_TIMEOUT_SECONDS = 20
API_MAX_RETRIES = 3
API_BACKOFF_SECONDS = 2.0
API_PER_PAGE = 20
API_TAG_ID = 0

CHECK_INTERVAL_SECONDS = 1 * 60 * 60
LOOKBACK_HOURS = 24

FETCH_RETRY_COUNT = API_MAX_RETRIES
CSV_RETRY_COUNT = 3
ARTICLE_RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = 2.0
ANALYZER_TIMEOUT_SECONDS = 300

# Re-export pipeline settings from their canonical location
from pipeline_config import (  # noqa: E402,F401
    PIPELINE_ON_API,
    PIPELINE_CATCHUP_ON_START,
    PIPELINE_INTERVAL_HOURS,
    PIPELINE_LOCK_TTL_SECONDS,
    PIPELINE_ADMIN_TOKEN,
    PIPELINE_STATE_ID,
    JOB_ID,
    ValidationResult,
    discover_groq_keys,
    validate_for_scheduler,
)
