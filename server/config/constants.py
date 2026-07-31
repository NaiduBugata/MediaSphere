"""Static constants: paths, filenames, separators, encoding defaults."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CHECK_INTERVAL_SECONDS = 1 * 60 * 60  # 1 hour
LOOKBACK_HOURS = 24

API_BASE_URL = "https://lokalnews.in/wp-json/wp/v2/posts"
API_TIMEOUT_SECONDS = 20
API_MAX_RETRIES = 3
API_BACKOFF_SECONDS = 2.0
API_PER_PAGE = 20
API_TAG_ID = 0

CSV_FILENAME = "narasaraopet_news.csv"
ARTICLE_FILENAME = "article.txt"
ANALYZER_FILENAME = "telugu_ai_news_analyzer.py"
OUTPUT_DIR_NAME = "output"
LOG_DIR_NAME = "logs"
PIPELINE_LOG_FILENAME = "pipeline.log"
PIPELINE_STATUS_FILENAME = "pipeline_status.json"

CSV_PATH = BASE_DIR / CSV_FILENAME
ARTICLE_PATH = BASE_DIR / ARTICLE_FILENAME
ANALYZER_PATH = BASE_DIR / ANALYZER_FILENAME
OUTPUT_PATH = BASE_DIR / OUTPUT_DIR_NAME
LOG_PATH = BASE_DIR / LOG_DIR_NAME
PIPELINE_LOG_PATH = LOG_PATH / PIPELINE_LOG_FILENAME
PIPELINE_STATUS_PATH = BASE_DIR / PIPELINE_STATUS_FILENAME

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

OUTPUT_ENCODING = "utf-8"
CSV_ENCODING = "utf-8-sig"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 10

ARTICLE_SEPARATOR = "===================================================="

FETCH_RETRY_COUNT = 3
CSV_RETRY_COUNT = 3
ARTICLE_RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = 2.0
ANALYZER_TIMEOUT_SECONDS = 300

OUTPUT_JSON_FILES = [
    "master_internal.json",
    "news_output.json",
    "statistics.json",
    "failed_articles.json",
]
