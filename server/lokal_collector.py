"""Legacy shim — canonical Lokal collector lives in ``sources.lokal``."""
# ruff: noqa: F401

from sources.lokal.api import build_page_url, create_session, fetch_page
from sources.lokal.collector import (
    configure_logging,
    get_output_path,
    logger,
    main,
    run,
    save_json,
)
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
from sources.lokal.extractor import fetch_last_24hr_news
from sources.lokal.normalizer import build_article_url, normalize_article, remove_duplicates
from sources.lokal.parser import parse_post_date

if __name__ == "__main__":
    main()
