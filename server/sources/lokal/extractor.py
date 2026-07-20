"""Extraction of recent posts from the paginated Lokal API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from sources.lokal.api import fetch_page
from sources.lokal.constants import LOOKBACK_HOURS
from sources.lokal.normalizer import normalize_article
from sources.lokal.parser import parse_post_date

logger = logging.getLogger("lokal_collector")


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
