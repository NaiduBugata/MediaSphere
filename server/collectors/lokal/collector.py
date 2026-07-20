"""Legacy shim — canonical Lokal collector lives in ``sources.lokal``."""
# ruff: noqa: F401

from sources.lokal.api import build_page_url, create_session, fetch_page
from sources.lokal.collector import (
    configure_logging,
    get_output_path,
    main,
    run,
    save_json,
)
from sources.lokal.extractor import fetch_last_24hr_news
from sources.lokal.normalizer import build_article_url, normalize_article, remove_duplicates
from sources.lokal.parser import parse_post_date
