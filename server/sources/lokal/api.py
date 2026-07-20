"""HTTP session and Lokal API page fetching."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sources.lokal.constants import (
    BACKOFF_FACTOR,
    BASE_URL,
    MAX_RETRIES,
    PAGE_SIZE,
    POST_TYPES,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_STATUS_CODES,
    TAG_ID,
)

logger = logging.getLogger("lokal_collector")


def create_session() -> requests.Session:
    """
    Create a reusable HTTP session with retry and default headers.

    Purpose:
        Configure transport-level retries with exponential backoff for transient
        HTTP failures while keeping a persistent session for connection reuse.

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
