"""Legacy shim — re-exports from database.mongo for backward compatibility.

All new code should import from `database.mongo` or `database` directly.
"""
# ruff: noqa: F401,F403,E402

from database.mongo import *  # noqa: F401,F403
from database.mongo import (
    _content_fingerprint,
    _current_timestamp,
    _normalize_title,
    _resolve_post_id,
    _resolve_youtube_post_id,
    _resolve_sakshi_post_id,
    get_client,
    get_collection,
    warmup,
    upsert_articles,
    upsert_youtube_articles,
    upsert_sakshi_articles,
    get_existing_youtube_video_ids,
    get_existing_sakshi_urls,
    filter_new_youtube_articles,
    build_postid_map,
    build_youtube_postid_map,
    build_sakshi_postid_map,
    sakshi_post_id,
    get_stats,
    archive_and_reset,
    MONGODB_URI,
    MONGODB_DB_NAME,
    MONGODB_COLLECTION,
    ARCHIVE_DIR,
)
