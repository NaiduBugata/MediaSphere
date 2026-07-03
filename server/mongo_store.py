"""Persist categorized news articles to MongoDB Atlas (MediaSphere)."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from config import OUTPUT_PATH

load_dotenv()

logger = logging.getLogger("mongo_store")

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "MediaSphere")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "articles")
ARCHIVE_DIR = OUTPUT_PATH / "archive"

_client: MongoClient | None = None


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip())


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
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)

    return _client


def get_collection() -> Collection:
    """
    Return the active articles collection, ensuring a unique post_id index.

    Returns:
        MongoDB collection handle for categorized articles.
    """
    client = get_client()
    collection = client[MONGODB_DB_NAME][MONGODB_COLLECTION]
    collection.create_index("post_id", unique=True)
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
        Dict with inserted, updated, matched, and total counts.
    """
    collection = get_collection()
    title_map = build_postid_map(collector_json_path)
    now = _current_timestamp()

    inserted = 0
    updated = 0
    matched = 0
    inserted_post_ids: list[Any] = []

    for article in news_articles:
        title = article.get("title", "")
        post_id, source_url, created_on = _resolve_post_id(title, title_map)

        document = {
            "post_id": post_id,
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
            "last_updated_at": now,
        }

        result = collection.update_one(
            {"post_id": post_id},
            {
                # New articles start un-emailed so the incremental notifier picks
                # them up exactly once. Never reset the flag on updates.
                "$set": document,
                "$setOnInsert": {"first_seen_at": now, "email_sent": False},
            },
            upsert=True,
        )

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
        "total": len(news_articles),
        "inserted_post_ids": inserted_post_ids,
    }


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
