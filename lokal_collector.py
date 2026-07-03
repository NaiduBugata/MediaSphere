"""Production-ready Lokal News Collector for Narasaraopet constituency news."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://telugu.getlokalapp.com/api/posts"
SOURCE_URL = "https://telugu.getlokalapp.com/api/posts"
WEBSITE_BASE_URL = "https://telugu.getlokalapp.com"

TAG_ID = 374
POST_TYPES = "1,2"
PAGE_SIZE = 100
LOOKBACK_HOURS = 24 * 7  # 7 days
CHECK_INTERVAL = 4 * 60 * 60  # 4 hours

OUTPUT_DIRECTORY = "data/lokal"
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

logger = logging.getLogger("lokal_collector")


def create_session() -> requests.Session:
    """
    Create a reusable HTTP session with retry and default headers.

    Purpose:
        Configure transport-level retries with exponential backoff for transient
        HTTP failures while keeping a persistent session for connection reuse.

    Parameters:
        None.

    Returns:
        A configured requests.Session ready for API calls.
    """
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=list(RETRY_STATUS_CODES),
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def build_page_url(page: int) -> str:
    """
    Build the paginated API URL for a given page number.

    Purpose:
        Centralize URL construction so query parameters stay consistent.

    Parameters:
        page: 1-based page index requested from the API.

    Returns:
        Fully qualified request URL for the page.
    """
    return (
        f"{BASE_URL}?tag_id={TAG_ID}&post_type={POST_TYPES}"
        f"&page_size={PAGE_SIZE}&page={page}"
    )


def fetch_page(session: requests.Session, page: int) -> Optional[Dict[str, Any]]:
    """
    Fetch one page of posts from the Lokal API.

    Purpose:
        Retrieve and parse a single API page while handling network, timeout,
        HTTP, and JSON errors without raising to the caller.

    Parameters:
        session: Reusable HTTP session.
        page: 1-based page number to fetch.

    Returns:
        Parsed JSON payload on success, otherwise None.
    """
    url = build_page_url(page)
    logger.info("Fetching page %s | URL: %s", page, url)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            logger.info("Page %s response status: %s", page, response.status_code)

            if response.status_code != 200:
                logger.warning(
                    "Page %s returned HTTP %s on attempt %s/%s",
                    page,
                    response.status_code,
                    attempt,
                    MAX_RETRIES,
                )
                if attempt >= MAX_RETRIES:
                    return None
                time.sleep(BACKOFF_FACTOR ** attempt)
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                logger.error("Invalid JSON on page %s: %s", page, exc)
                return None

            if not isinstance(payload, dict):
                logger.error("Unexpected schema on page %s: root is not an object", page)
                return None

            return payload

        except requests.Timeout as exc:
            logger.warning(
                "Timeout on page %s attempt %s/%s: %s",
                page,
                attempt,
                MAX_RETRIES,
                exc,
            )
        except requests.RequestException as exc:
            logger.warning(
                "Network error on page %s attempt %s/%s: %s",
                page,
                attempt,
                MAX_RETRIES,
                exc,
            )

        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_FACTOR ** attempt)

    logger.error("Failed to fetch page %s after %s attempts", page, MAX_RETRIES)
    return None


def parse_post_date(value: Any) -> Optional[datetime]:
    """
    Parse a post timestamp from common ISO-8601 formats.

    Purpose:
        Normalize API timestamps for reliable cutoff comparisons.

    Parameters:
        value: Raw created_on value from the API.

    Returns:
        Timezone-aware datetime on success, otherwise None.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)

    return parsed.astimezone(timezone.utc)


def build_article_url(post: Dict[str, Any]) -> str:
    """
    Build a best-effort public URL for a post.

    Purpose:
        Provide a usable link even when the API does not expose the full
        canonical path segments.

    Parameters:
        post: Raw post object from the API.

    Returns:
        Best-effort article URL string.
    """
    custom_link = post.get("custom_link")
    if custom_link:
        return str(custom_link)

    slug = str(post.get("slug") or "").strip()
    post_id = post.get("id")
    if slug and post_id is not None:
        return f"{WEBSITE_BASE_URL}/{slug}-{post_id}"

    if post_id is not None:
        return f"{WEBSITE_BASE_URL}/post/{post_id}"

    return ""


def normalize_article(post: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize one API post into the collector output schema.

    Purpose:
        Map API fields to the saved article structure while preserving the
        complete original payload in raw.

    Parameters:
        post: Raw post dictionary from the API results list.

    Returns:
        Normalized article dictionary, or None when required fields are missing.
    """
    if not isinstance(post, dict):
        logger.warning("Skipped post with unexpected type: %s", type(post).__name__)
        return None

    post_id = post.get("id")
    if post_id is None:
        logger.warning("Skipped post without id")
        return None

    created_on = post.get("created_on")
    if created_on is None:
        logger.warning("Skipped post id=%s without created_on", post_id)
        return None

    return {
        "id": post_id,
        "title": post.get("title") or "",
        "content": post.get("content") or "",
        "created_on": str(created_on),
        "url": build_article_url(post),
        "raw": post,
    }


def remove_duplicates(articles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Remove duplicate articles by id, keeping the newest created_on value.

    Purpose:
        Ensure pagination overlap does not produce duplicate saved records.

    Parameters:
        articles: List of normalized article dictionaries.

    Returns:
        Tuple of (deduplicated articles, duplicates removed count).
    """
    newest_by_id: Dict[Any, Dict[str, Any]] = {}

    for article in articles:
        article_id = article.get("id")
        if article_id is None:
            continue

        existing = newest_by_id.get(article_id)
        if existing is None:
            newest_by_id[article_id] = article
            continue

        existing_dt = parse_post_date(existing.get("created_on"))
        current_dt = parse_post_date(article.get("created_on"))

        if current_dt is not None and (existing_dt is None or current_dt >= existing_dt):
            newest_by_id[article_id] = article

    deduplicated = list(newest_by_id.values())
    duplicates_removed = len(articles) - len(deduplicated)
    return deduplicated, duplicates_removed


def fetch_last_24hr_news(session: requests.Session) -> List[Dict[str, Any]]:
    """
    Fetch all posts from the last configured lookback window.

    Purpose:
        Paginate through the API until no posts remain or an older-than-cutoff
        post is encountered, collecting normalized articles along the way.

    Parameters:
        session: Reusable HTTP session.

    Returns:
        List of normalized article dictionaries within the lookback window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    articles: List[Dict[str, Any]] = []
    page = 1
    skipped = 0

    while True:
        payload = fetch_page(session, page)
        if payload is None:
            logger.error("Stopping pagination because page %s could not be fetched", page)
            break

        results = payload.get("results")
        if not isinstance(results, list):
            logger.error("Unexpected schema on page %s: results is not a list", page)
            break

        if not results:
            logger.info("No posts returned on page %s; stopping pagination", page)
            break

        received = len(results)
        accepted = 0
        stop_fetching = False

        for post in results:
            if not isinstance(post, dict):
                skipped += 1
                logger.warning("Skipped non-object post on page %s", page)
                continue

            post_time = parse_post_date(post.get("created_on"))
            if post_time is None:
                skipped += 1
                logger.warning(
                    "Skipped post id=%s due to unparseable created_on: %s",
                    post.get("id"),
                    post.get("created_on"),
                )
                continue

            if post_time < cutoff:
                stop_fetching = True
                break

            normalized = normalize_article(post)
            if normalized is None:
                skipped += 1
                continue

            articles.append(normalized)
            accepted += 1

        logger.info(
            "Page %s summary | posts received: %s | posts accepted: %s | articles skipped so far: %s",
            page,
            received,
            accepted,
            skipped,
        )

        if stop_fetching:
            logger.info("Reached cutoff on page %s; stopping pagination", page)
            break

        if not payload.get("next"):
            logger.info("No next page after page %s; stopping pagination", page)
            break

        page += 1

    logger.info("Fetch complete | raw articles collected: %s | articles skipped: %s", len(articles), skipped)
    return articles


def get_output_path() -> Path:
    """
    Resolve the JSON output file path.

    Purpose:
        Provide a single source of truth for where collector output is written.

    Parameters:
        None.

    Returns:
        Path object for the output JSON file.
    """
    return Path(OUTPUT_DIRECTORY) / OUTPUT_FILENAME


def save_json(articles: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Save collected articles to a structured JSON file.

    Purpose:
        Persist the collector envelope and article list with UTF-8 Telugu support.

    Parameters:
        articles: Deduplicated normalized article list.
        output_path: Destination JSON file path.

    Returns:
        None.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collector": COLLECTOR_NAME,
        "source": SOURCE_URL,
        "tag_id": TAG_ID,
        "lookback_hours": LOOKBACK_HOURS,
        "total_articles": len(articles),
        "articles": articles,
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    logger.info("Saved %s articles to %s", len(articles), output_path)


def run() -> None:
    """
    Execute one full collector cycle.

    Purpose:
        Fetch recent news, deduplicate, save JSON, and log execution metrics
        without terminating the scheduler on recoverable errors.

    Parameters:
        None.

    Returns:
        None.
    """
    started_at = time.perf_counter()
    logger.info("Collector cycle started")

    try:
        session = create_session()
        raw_articles = fetch_last_24hr_news(session)
        articles, duplicates_removed = remove_duplicates(raw_articles)
        output_path = get_output_path()
        save_json(articles, output_path)

        elapsed = time.perf_counter() - started_at
        logger.info("Duplicates removed: %s", duplicates_removed)
        logger.info("Total saved: %s", len(articles))
        logger.info("Execution time: %.2f seconds", elapsed)
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        logger.exception("Collector cycle failed after %.2f seconds: %s", elapsed, exc)


def configure_logging() -> None:
    """
    Configure module logging for production use.

    Purpose:
        Ensure consistent log formatting for scheduled collector runs.

    Parameters:
        None.

    Returns:
        None.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> None:
    """
    Start the scheduled collector loop.

    Purpose:
        Run the collector every CHECK_INTERVAL seconds until interrupted.

    Parameters:
        None.

    Returns:
        None.
    """
    configure_logging()
    logger.info("Lokal News Collector started")

    while True:
        run()
        logger.info("Sleeping for %s seconds (%s hours)", CHECK_INTERVAL, CHECK_INTERVAL / 3600)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
