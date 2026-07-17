"""Database layer: MongoDB connection, repositories, and indexes."""

from database.mongo import (  # noqa: F401
    get_client,
    get_collection,
    warmup,
    upsert_articles,
    upsert_youtube_articles,
    upsert_sakshi_articles,
    get_existing_youtube_video_ids,
    get_existing_sakshi_urls,
    delete_sakshi_articles,
    count_by_source,
    filter_new_youtube_articles,
    build_postid_map,
    build_youtube_postid_map,
    build_sakshi_postid_map,
    get_stats,
    archive_and_reset,
    MONGODB_URI,
    MONGODB_DB_NAME,
    MONGODB_COLLECTION,
)
