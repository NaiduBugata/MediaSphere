"""Sakshi collector configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


# ---- Sakshi ----
SAKSHI_ENABLED = _truthy("SAKSHI_ENABLED", "true")
SAKSHI_TAG_URL = os.getenv(
    "SAKSHI_TAG_URL",
    "https://www.sakshi.com/tags/narasaraopet",
).strip()
SAKSHI_BASE_URL = os.getenv("SAKSHI_BASE_URL", "https://www.sakshi.com").rstrip("/")
SAKSHI_REQUEST_DELAY_SECONDS = max(0.5, _float_env("SAKSHI_REQUEST_DELAY_SECONDS", 1.5))
SAKSHI_TIMEOUT_SECONDS = max(5, _int_env("SAKSHI_TIMEOUT_SECONDS", 30))
SAKSHI_MAX_ARTICLES_PER_RUN = max(1, _int_env("SAKSHI_MAX_ARTICLES_PER_RUN", 20))
SAKSHI_MAX_RETRIES = max(1, _int_env("SAKSHI_MAX_RETRIES", 3))
SAKSHI_CONSTITUENCY_SCORE_THRESHOLD = max(1, _int_env("SAKSHI_CONSTITUENCY_SCORE_THRESHOLD", 6))
SAKSHI_AI_VALIDATION = _truthy("SAKSHI_AI_VALIDATION", "true")
LOCATION_DICTIONARY_PATH = BASE_DIR / "config" / "location_dictionary.json"
SAKSHI_OUTPUT_DIR = DATA_DIR / "sakshi"
SAKSHI_OUTPUT_FILE = SAKSHI_OUTPUT_DIR / "narasaraopet_news.json"
SAKSHI_ARTICLE_PATH = SAKSHI_OUTPUT_DIR / "article.txt"
SAKSHI_ANALYZER_OUTPUT_DIR = BASE_DIR / "output" / "sakshi"
SAKSHI_CHECKPOINT_FILE = SAKSHI_ANALYZER_OUTPUT_DIR / "checkpoint.json"
SAKSHI_USER_AGENT = os.getenv(
    "SAKSHI_USER_AGENT",
    "MediaSphereBot/1.0 (+https://github.com/NaiduBugata/MediaSphere; news aggregation)",
)

# Selectors (overridable if Sakshi changes markup)
SAKSHI_ARTICLE_LINK_SELECTOR = os.getenv(
    "SAKSHI_ARTICLE_LINK_SELECTOR",
    "a[href]",
)
SAKSHI_ARTICLE_BODY_SELECTOR = os.getenv(
    "SAKSHI_ARTICLE_BODY_SELECTOR",
    "div.story-content, div.article-content, article .content, div#storyBody, div.field-name-body",
)
SAKSHI_TITLE_SELECTOR = os.getenv(
    "SAKSHI_TITLE_SELECTOR",
    "h1.story-title, h1.article-title, h1.title, h1",
)

TRANSIENT_HTTP_STATUSES = frozenset({500, 502, 503, 504})
NON_RETRYABLE_HTTP_STATUSES = frozenset({400, 403, 404})

SKIP_URL_SUBSTRINGS = (
    "/videos/",
    "/video/",
    "/gallery/",
    "/photo/",
    "/photos/",
    "/advertise",
    "/ads/",
    "javascript:",
    "mailto:",
    "#",
)

# Tag pages mix homepage/sidebar noise. Deprioritize these paths unless the URL
# itself contains a constituency location keyword.
NON_LOCAL_URL_PATH_MARKERS = (
    "/sports/",
    "/business/",
    "/cartoon/",
    "/national/",
    "/international/",
    "/family/",
    "/cinema/",
    "/entertainment/",
    "/technology/",
    "/astrology/",
    "/movies/",
    "/tollywood/",
    "/editorial/",
)
