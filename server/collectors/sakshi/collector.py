"""Legacy shim — canonical Sakshi collector lives in ``sources.sakshi``."""
# ruff: noqa: F401

from sources.sakshi.collector import (
    PermanentHttpError,
    SakshiCollector,
    TransientHttpError,
    _get_html,
    _session,
    collect_sakshi_articles,
    get_output_path,
    logger,
    run,
    save_json,
)
from sources.sakshi.extractor import extract_article
from sources.sakshi.normalizer import normalize_sakshi_article
from sources.sakshi.parser import (
    _is_article_url,
    _is_section_hub_url,
    _is_skip_url,
    _link_priority,
    _load_url_priority_keywords,
    _meta_content,
    _parse_datetime,
    _stable_article_id,
    _text_or_empty,
    _url_has_location_keyword,
)
