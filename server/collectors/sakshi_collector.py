"""Legacy shim — re-exports from collectors.sakshi.collector."""
# ruff: noqa: F401,F403

from collectors.sakshi.collector import *  # noqa: F401,F403
from collectors.sakshi.collector import (
    PermanentHttpError,
    TransientHttpError,
    SakshiCollector,
    collect_sakshi_articles,
    get_output_path,
    save_json,
    run,
    _get_html,
    _is_article_url,
    _is_skip_url,
    _stable_article_id,
    _parse_datetime,
    _meta_content,
    _text_or_empty,
    _session,
)
