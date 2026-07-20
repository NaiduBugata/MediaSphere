"""Legacy shim — re-exports from sources.youtube.config."""
# ruff: noqa: F401,F403

from sources.youtube.config import *  # noqa: F401,F403
from sources.youtube.config import (
    ARTICLE_PATH,
    BASE_DIR,
    CHECKPOINT_FILE,
    DATA_DIR,
    KEYWORDS,
    NEWS_JSON,
    OUTPUT_DIR,
    PIPELINE_LOG,
    SEARCH_KEYWORDS,
    TRANSCRIPT_LANGUAGES,
    TRANSCRIPTS_JSON,
    VIDEOS_JSON,
    YOUTUBE_API_KEY,
    YOUTUBE_CHECK_INTERVAL,
    YOUTUBE_ENABLED,
    YOUTUBE_MAX_CONTENT_CHARS,
    YOUTUBE_MAX_NEW_PER_RUN,
    YOUTUBE_MAX_RESULTS_PER_KEYWORD,
    YOUTUBE_MIN_CONTENT_CHARS,
    YOUTUBE_SEARCH_PERIOD_DAYS,
)
