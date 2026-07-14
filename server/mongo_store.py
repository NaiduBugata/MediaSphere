"""Persist categorized news articles to MongoDB Atlas (MediaSphere)."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from config import OUTPUT_PATH

load_dotenv()

logger = logging.getLogger("mongo_store")

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "MediaSphere")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "articles")
ARCHIVE_DIR = OUTPUT_PATH / "archive"

_client: MongoClient | None = None
_client_lock = threading.Lock()

# Pre-import dnspython for mongodb+srv URIs so concurrent first-use does not
# race on the import lock inside pymongo (seen as gunicorn worker timeouts).
try:
    import dns  # noqa: F401
except ImportError:
    logger.warning("dnspython not installed; mongodb+srv URIs may fail.")


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_title(title: str) -> str:
    text = title.strip().replace("…", "...")
    return re.sub(r"\s+", " ", text)


def get_client() -> MongoClient:
    """
    Return a singleton MongoDB client configured from environment variables.

    Returns:
        Connected MongoClient instance.

    Raises:
        ValueError: When MONGODB_URI is not configured.
    """
    global _client

    if not MONGODB_URI:
        raise ValueError("MONGODB_URI is not set in environment or .env")

    if _client is None:
        with _client_lock:
            if _client is None:
                _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)

    return _client


def warmup() -> None:
    """Verify MongoDB connectivity at startup (call once from wsgi.py)."""
    if not MONGODB_URI:
        logger.warning("MONGODB_URI not set; skipping MongoDB warmup.")
        return
    try:
        get_client().admin.command("ping")
        logger.info("MongoDB connection verified.")
    except ServerSelectionTimeoutError as exc:
        logger.error("MongoDB warmup failed (server selection timeout): %s", exc)
        raise
    except Exception as exc:
        logger.error("MongoDB warmup failed: %s", exc)
        raise


def _content_fingerprint(source: str, title: str, source_url: str | None) -> str:
    normalized = _normalize_title(title)
    url = (source_url or "").strip()
    raw = f"{source}|{normalized}|{url}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def get_collection() -> Collection:
    """
    Return the active articles collection, ensuring a unique post_id index.

    Returns:
        MongoDB collection handle for categorized articles.
    """
    client = get_client()
    collection = client[MONGODB_DB_NAME][MONGODB_COLLECTION]
    collection.create_index("post_id", unique=True)
    collection.create_index([("source", 1), ("created_on", -1)])
    collection.create_index("content_fingerprint", unique=True, sparse=True)
    return collection


def build_postid_map(collector_json_path: Path | str) -> dict[str, dict[str, Any]]:
    """
    Build a title-to-metadata map from the Lokal collector JSON.

    Parameters:
        collector_json_path: Path to narasaraopet_news.json.

    Returns:
        Mapping of normalized title -> {post_id, url, created_on, raw_title}.
    """
    payload = json.loads(Path(collector_json_path).read_text(encoding="utf-8"))
    articles = payload.get("articles", [])

    title_map: dict[str, dict[str, Any]] = {}
    for article in articles:
        title = article.get("title", "")
        if not title:
            continue

        entry = {
            "post_id": article["id"],
            "url": article.get("url"),
            "created_on": article.get("created_on"),
            "raw_title": title,
        }

        title_map[title] = entry
        normalized = _normalize_title(title)
        if normalized not in title_map:
            title_map[normalized] = entry

    return title_map


def _resolve_post_id(title: str, title_map: dict[str, dict[str, Any]]) -> tuple[int | str, str | None, str | None]:
    """
    Resolve post_id and source metadata for a categorized article title.

    Parameters:
        title: Article title from news_output.json.
        title_map: Title map built from collector JSON.

    Returns:
        Tuple of (post_id, source_url, created_on).
    """
    normalized = _normalize_title(title)

    if title in title_map:
        meta = title_map[title]
    elif normalized in title_map:
        meta = title_map[normalized]
    else:
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        logger.warning("No collector match for title %r; using hash post_id %s", title, digest)
        return f"hash_{digest}", None, None

    return meta["post_id"], meta.get("url"), meta.get("created_on")


def upsert_articles(
    news_articles: list[dict[str, Any]],
    collector_json_path: Path | str,
) -> dict[str, int]:
    """
    Upsert categorized articles into MongoDB by Lokal post_id.

    Parameters:
        news_articles: Parsed news_output.json payload.
        collector_json_path: Path to collector JSON for post_id resolution.

    Returns:
        Dict with inserted, updated, matched, duplicates, and total counts.
    """
    from retry_utils import retry_call

    title_map = build_postid_map(collector_json_path)
    now = _current_timestamp()

    inserted = 0
    updated = 0
    matched = 0
    duplicates = 0
    inserted_post_ids: list[Any] = []

    def _get_collection() -> Collection:
        return get_collection()

    collection = retry_call(_get_collection, label="mongo.get_collection")

    for article in news_articles:
        title = article.get("title", "")
        post_id, source_url, created_on = _resolve_post_id(title, title_map)
        fingerprint = _content_fingerprint("lokal", title, source_url)

        document = {
            "post_id": post_id,
            "source": "lokal",
            "title": title,
            "sentiment": article.get("sentiment"),
            "category": article.get("category"),
            "subcategory": article.get("subcategory"),
            "summary": article.get("summary"),
            "problem": article.get("problem"),
            "problem_id": article.get("problem_id"),
            "location": article.get("location"),
            "entities": article.get("entities"),
            "keywords": article.get("keywords"),
            "source_url": source_url,
            "created_on": created_on,
            "content_fingerprint": fingerprint,
            "last_updated_at": now,
        }

        def _upsert(pid: Any = post_id, doc: dict[str, Any] = document) -> Any:
            return collection.update_one(
                {"post_id": pid},
                {
                    # New articles start un-emailed so the incremental notifier picks
                    # them up exactly once. Never reset the flag on updates.
                    "$set": doc,
                    "$setOnInsert": {"first_seen_at": now, "email_sent": False},
                },
                upsert=True,
            )

        try:
            result = retry_call(_upsert, label=f"mongo.upsert_lokal:{post_id}")
        except DuplicateKeyError:
            duplicates += 1
            logger.info(
                "Duplicate skipped (fingerprint/post_id) for lokal title=%r post_id=%s",
                title[:80],
                post_id,
            )
            continue

        if result.upserted_id is not None:
            inserted += 1
            inserted_post_ids.append(post_id)
        elif result.modified_count > 0:
            updated += 1
        else:
            matched += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "matched": matched,
        "duplicates": duplicates,
        "total": len(news_articles),
        "inserted_post_ids": inserted_post_ids,
    }


YOUTUBE_POST_ID_PREFIX = "yt_"


def youtube_post_id(video_id: str) -> str:
    return f"{YOUTUBE_POST_ID_PREFIX}{video_id}"


def get_existing_youtube_video_ids() -> set[str]:
    """Return video_ids already stored from YouTube (post_id yt_*)."""
    collection = get_collection()
    ids: set[str] = set()
    cursor = collection.find({"source": "youtube"}, {"post_id": 1})
    for doc in cursor:
        post_id = doc.get("post_id")
        if isinstance(post_id, str) and post_id.startswith(YOUTUBE_POST_ID_PREFIX):
            ids.add(post_id[len(YOUTUBE_POST_ID_PREFIX):])
    return ids


def build_youtube_postid_map(collector_json_path: Path | str) -> dict[str, dict[str, Any]]:
    """Build title-to-metadata map from YouTube collector JSON."""
    payload = json.loads(Path(collector_json_path).read_text(encoding="utf-8"))
    articles = payload.get("articles", [])

    title_map: dict[str, dict[str, Any]] = {}
    for article in articles:
        title = article.get("title", "")
        video_id = article.get("video_id") or article.get("id")
        if not title or not video_id:
            continue

        entry = {
            "post_id": youtube_post_id(str(video_id)),
            "video_id": str(video_id),
            "url": article.get("url"),
            "created_on": article.get("created_on"),
            "channel": article.get("channel"),
            "raw_title": title,
        }
        title_map[title] = entry
        normalized = _normalize_title(title)
        if normalized not in title_map:
            title_map[normalized] = entry
        title_map[str(video_id)] = entry

    return title_map


def _resolve_youtube_post_id(
    title: str,
    title_map: dict[str, dict[str, Any]],
) -> tuple[str, str | None, str | None, str | None]:
    normalized = _normalize_title(title)

    if title in title_map:
        meta = title_map[title]
    elif normalized in title_map:
        meta = title_map[normalized]
    else:
        # Analyzer may truncate long titles with "..." — match collector prefix.
        prefix = normalized.rstrip(".")
        meta = None
        for collector_title, entry in title_map.items():
            if not isinstance(collector_title, str) or collector_title.startswith("yt_"):
                continue
            collector_norm = _normalize_title(collector_title)
            if collector_norm.startswith(prefix) or prefix.startswith(collector_norm[: min(len(prefix), len(collector_norm))]):
                meta = entry
                break
        if meta is None:
            digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
            logger.warning("No YouTube collector match for title %r; using hash post_id", title)
            return f"{YOUTUBE_POST_ID_PREFIX}hash_{digest}", None, None, None

    return (
        meta["post_id"],
        meta.get("url"),
        meta.get("created_on"),
        meta.get("channel"),
    )


def upsert_youtube_articles(
    news_articles: list[dict[str, Any]],
    collector_json_path: Path | str,
) -> dict[str, int]:
    """Upsert categorized YouTube articles into MongoDB."""
    from retry_utils import retry_call

    title_map = build_youtube_postid_map(collector_json_path)
    now = _current_timestamp()

    inserted = 0
    updated = 0
    matched = 0
    duplicates = 0
    inserted_post_ids: list[Any] = []

    collection = retry_call(get_collection, label="mongo.get_collection.youtube")

    for article in news_articles:
        title = article.get("title", "")
        post_id, source_url, created_on, channel = _resolve_youtube_post_id(title, title_map)
        fingerprint = _content_fingerprint("youtube", title, source_url)

        document = {
            "post_id": post_id,
            "source": "youtube",
            "title": title,
            "sentiment": article.get("sentiment"),
            "category": article.get("category"),
            "subcategory": article.get("subcategory"),
            "summary": article.get("summary"),
            "problem": article.get("problem"),
            "problem_id": article.get("problem_id"),
            "location": article.get("location"),
            "entities": article.get("entities"),
            "keywords": article.get("keywords"),
            "source_url": source_url,
            "channel": channel,
            "created_on": created_on,
            "content_fingerprint": fingerprint,
            "last_updated_at": now,
        }

        def _upsert(pid: str = post_id, doc: dict[str, Any] = document) -> Any:
            return collection.update_one(
                {"post_id": pid},
                {
                    "$set": doc,
                    "$setOnInsert": {"first_seen_at": now, "email_sent": False},
                },
                upsert=True,
            )

        try:
            result = retry_call(_upsert, label=f"mongo.upsert_youtube:{post_id}")
        except DuplicateKeyError:
            duplicates += 1
            logger.info(
                "Duplicate skipped (fingerprint/post_id) for youtube title=%r post_id=%s",
                title[:80],
                post_id,
            )
            continue

        if result.upserted_id is not None:
            inserted += 1
            inserted_post_ids.append(post_id)
        elif result.modified_count > 0:
            updated += 1
        else:
            matched += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "matched": matched,
        "duplicates": duplicates,
        "total": len(news_articles),
        "inserted_post_ids": inserted_post_ids,
    }


def filter_new_youtube_articles(
    collector_json_path: Path | str,
    max_count: int | None = None,
) -> tuple[Path, list[dict[str, Any]]]:
    """
    Return collector path and articles whose video_ids are not yet in MongoDB.

    Writes a filtered envelope to youtube_news_new.json for the analyzer batch.
    """
    payload = json.loads(Path(collector_json_path).read_text(encoding="utf-8"))
    existing = get_existing_youtube_video_ids()
    new_articles = [
        a for a in payload.get("articles", [])
        if str(a.get("video_id") or a.get("id")) not in existing
    ]
    # Newest published first so latest constituency news is analyzed before older backlog.
    new_articles.sort(key=lambda a: a.get("created_on") or "", reverse=True)

    if max_count is not None and max_count > 0:
        new_articles = new_articles[:max_count]

    filtered_path = Path(collector_json_path).parent / "youtube_news_new.json"
    filtered_envelope = {
        **{k: v for k, v in payload.items() if k != "articles"},
        "articles": new_articles,
        "new_count": len(new_articles),
    }
    filtered_path.write_text(json.dumps(filtered_envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return filtered_path, new_articles


def get_stats() -> dict[str, Any]:
    """
    Return basic statistics for the active articles collection.

    Returns:
        Dict with database name, collection name, and document count.
    """
    collection = get_collection()
    return {
        "database": MONGODB_DB_NAME,
        "collection": MONGODB_COLLECTION,
        "count": collection.count_documents({}),
    }


def archive_and_reset(archive: bool = True) -> dict[str, Any]:
    """
    Archive the active collection and clear it for a fresh monitoring cycle.

    Parameters:
        archive: When True, copy docs to archive collection and export JSON.

    Returns:
        Summary dict with archived count and archive destinations.
    """
    collection = get_collection()
    docs = list(collection.find({}, {"_id": 0}))

    summary: dict[str, Any] = {
        "archived_count": len(docs),
        "archive_collection": None,
        "export_path": None,
        "cleared": False,
    }

    if archive and docs:
        timestamp = datetime.now(timezone.utc)
        archive_name = f"archive_{timestamp.strftime('%Y%m')}"
        archive_collection = get_client()[MONGODB_DB_NAME][archive_name]

        for doc in docs:
            doc_copy = dict(doc)
            doc_copy["archived_at"] = timestamp.isoformat()
            try:
                archive_collection.insert_one(doc_copy)
            except DuplicateKeyError:
                archive_collection.replace_one({"post_id": doc_copy["post_id"]}, doc_copy)

        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        export_path = ARCHIVE_DIR / f"articles_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        export_path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")

        summary["archive_collection"] = archive_name
        summary["export_path"] = str(export_path)

    delete_result = collection.delete_many({})
    summary["cleared"] = True
    summary["deleted_count"] = delete_result.deleted_count

    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MediaSphere MongoDB article store")
    parser.add_argument("--stats", action="store_true", help="Print collection statistics")
    parser.add_argument("--reset", action="store_true", help="Archive and clear the active collection")
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Clear the collection without archiving (use with --reset)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        stream=sys.stdout,
    )

    args = parse_args(argv)

    try:
        if args.stats:
            stats = get_stats()
            print(
                f"Database: {stats['database']} | "
                f"Collection: {stats['collection']} | "
                f"Documents: {stats['count']}"
            )
            return 0

        if args.reset:
            summary = archive_and_reset(archive=not args.no_archive)
            logger.info(
                "Reset complete | archived: %s | deleted: %s | export: %s | archive_collection: %s",
                summary["archived_count"],
                summary.get("deleted_count", 0),
                summary.get("export_path"),
                summary.get("archive_collection"),
            )
            return 0

        parser = argparse.ArgumentParser(description="MediaSphere MongoDB article store")
        parser.print_help()
        return 1

    except Exception as exc:
        logger.exception("MongoDB operation failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
