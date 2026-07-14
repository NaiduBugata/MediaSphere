"""Lokal collector configuration."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

BASE_URL = "https://telugu.getlokalapp.com/api/posts"
SOURCE_URL = "https://telugu.getlokalapp.com/api/posts"
WEBSITE_BASE_URL = "https://telugu.getlokalapp.com"

TAG_ID = 374
POST_TYPES = "1,2"
PAGE_SIZE = 100
LOOKBACK_HOURS = 24 * 7  # 7 days

PIPELINE_INTERVAL_HOURS = float(os.getenv("PIPELINE_INTERVAL_HOURS", "1"))
CHECK_INTERVAL = int(PIPELINE_INTERVAL_HOURS * 60 * 60)

OUTPUT_DIRECTORY = DATA_DIR / "lokal"
OUTPUT_FILENAME = "narasaraopet_news.json"

REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)

USER_AGENT = "Mozilla/5.0 (compatible; LokalNewsCollector/1.0)"
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

COLLECTOR_NAME = "Lokal News Collector"
