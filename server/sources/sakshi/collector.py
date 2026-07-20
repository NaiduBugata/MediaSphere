"""Sakshi.com Narasaraopet tag-page collector (no scheduling / no Mongo writes)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from pipeline.retry import is_transient, retry_call
from sources.base.base_collector import BaseCollector
from sources.sakshi import config as sakshi_config
from sources.sakshi.extractor import extract_article
from sources.sakshi.normalizer import normalize_sakshi_article
from sources.sakshi.parser import (
    _is_article_url,
    _is_section_hub_url,
    _link_priority,
    _load_url_priority_keywords,
)
from sources.sakshi.validator import ConstituencyValidator, get_validator

logger = logging.getLogger("collectors.sakshi")


class PermanentHttpError(Exception):
    """Raised for non-retryable HTTP responses (400/403/404)."""

    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} for {url}")


class TransientHttpError(Exception):
    """Raised for retryable HTTP responses (5xx)."""

    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} for {url}")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": sakshi_config.SAKSHI_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "te,en;q=0.8",
        }
    )
    return session


def _get_html(session: requests.Session, url: str) -> str:
    def _do_get() -> str:
        response = session.get(url, timeout=sakshi_config.SAKSHI_TIMEOUT_SECONDS)
        if response.status_code in sakshi_config.NON_RETRYABLE_HTTP_STATUSES:
            raise PermanentHttpError(response.status_code, url)
        if response.status_code in sakshi_config.TRANSIENT_HTTP_STATUSES:
            raise TransientHttpError(response.status_code, url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    try:
        return retry_call(
            _do_get,
            retries=sakshi_config.SAKSHI_MAX_RETRIES,
            base_delay=1.0,
            exceptions=(TransientHttpError, TimeoutError, ConnectionError, OSError, requests.RequestException),
            label=f"sakshi.get:{url[:80]}",
        )
    except PermanentHttpError:
        raise
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status in sakshi_config.NON_RETRYABLE_HTTP_STATUSES:
            raise PermanentHttpError(status or 0, url) from exc
        if status in sakshi_config.TRANSIENT_HTTP_STATUSES or is_transient(exc):
            raise TransientHttpError(status or 0, url) from exc
        raise


class SakshiCollector(BaseCollector):
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        existing_urls: set[str] | None = None,
        request_delay: float | None = None,
        max_articles: int | None = None,
        validator: ConstituencyValidator | None = None,
    ) -> None:
        self.session = session or _session()
        self.existing_urls = existing_urls or set()
        self.request_delay = (
            sakshi_config.SAKSHI_REQUEST_DELAY_SECONDS if request_delay is None else request_delay
        )
        self.max_articles = (
            sakshi_config.SAKSHI_MAX_ARTICLES_PER_RUN if max_articles is None else max_articles
        )
        self.validator = validator or get_validator()
        self.filter_stats: dict[str, Any] = {
            "fetched": 0,
            "accepted": 0,
            "rejected": 0,
            "rejected_reasons": {},
            "scores": [],
        }

    def fetch_links(self) -> list[str]:
        logger.info("Starting Sakshi collector")
        logger.info("Tag page download: %s", sakshi_config.SAKSHI_TAG_URL)
        html = _get_html(self.session, sakshi_config.SAKSHI_TAG_URL)
        soup = BeautifulSoup(html, "lxml")
        ranked: list[tuple[int, int, str]] = []
        seen: set[str] = set()
        keywords = _load_url_priority_keywords()

        for index, anchor in enumerate(soup.select(sakshi_config.SAKSHI_ARTICLE_LINK_SELECTOR)):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(sakshi_config.SAKSHI_BASE_URL + "/", href)
            absolute = absolute.split("#")[0]
            if absolute in seen:
                continue
            if not _is_article_url(absolute):
                continue
            if _is_section_hub_url(absolute):
                continue
            seen.add(absolute)
            anchor_text = " ".join(anchor.get_text(" ", strip=True).split())
            priority = _link_priority(absolute, anchor_text, keywords)
            # Only fetch links that mention a PC place name in the URL/anchor.
            # Sidebar/homepage noise (priority 10–40) is dropped before download.
            if priority < 100:
                continue
            ranked.append((priority, -index, absolute))

        ranked.sort(reverse=True)
        found = [url for _, _, url in ranked]
        high = sum(1 for p, _, _ in ranked if p >= 100)
        logger.info(
            "%s links found after constituency URL ranking (%s location-priority)",
            len(found),
            high,
        )
        return found

    def fetch_article(self, url: str) -> dict[str, Any] | None:
        logger.info("Extracting article: %s", url)
        try:
            html = _get_html(self.session, url)
        except PermanentHttpError as exc:
            logger.warning("Skipping permanent HTTP error: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to download article %s: %s", url, exc)
            return None

        return extract_article(html, url)

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return normalize_sakshi_article(raw)

    def collect(self) -> list[dict[str, Any]]:
        links = self.fetch_links()
        pending = [url for url in links if url not in self.existing_urls]
        pending = pending[: self.max_articles]
        logger.info("%s new articles to fetch (of %s links)", len(pending), len(links))

        articles: list[dict[str, Any]] = []
        self.filter_stats = {
            "fetched": 0,
            "accepted": 0,
            "rejected": 0,
            "rejected_reasons": {},
            "scores": [],
        }

        for index, url in enumerate(pending):
            if index > 0 and self.request_delay > 0:
                time.sleep(self.request_delay)
            raw = self.fetch_article(url)
            if not raw:
                continue

            self.filter_stats["fetched"] += 1
            validation = self.validator.validate_article(raw)
            self.filter_stats["scores"].append(validation.score)

            if not validation.valid:
                self.filter_stats["rejected"] += 1
                reasons = self.filter_stats["rejected_reasons"]
                reasons[validation.reason] = reasons.get(validation.reason, 0) + 1
                logger.info(
                    "Rejected Sakshi article | score=%s | reason=%s | title=%r",
                    validation.score,
                    validation.reason,
                    (raw.get("title") or "")[:80],
                )
                continue

            self.filter_stats["accepted"] += 1
            raw["_constituency_validation"] = validation.to_dict()
            logger.info(
                "Accepted Sakshi article | score=%s | reason=%s | title=%r",
                validation.score,
                validation.reason,
                (raw.get("title") or "")[:80],
            )
            articles.append(self.normalize(raw))

        logger.info(
            "Finished Sakshi collect | fetched=%s | accepted=%s | rejected=%s | articles=%s",
            self.filter_stats["fetched"],
            self.filter_stats["accepted"],
            self.filter_stats["rejected"],
            len(articles),
        )
        return articles


def collect_sakshi_articles(
    *,
    existing_urls: set[str] | None = None,
    request_delay: float | None = None,
    max_articles: int | None = None,
    collector_out: list | None = None,
) -> list[dict[str, Any]]:
    """Public collector entry: returns normalized constituency-validated Sakshi articles only."""
    urls = existing_urls
    if urls is None:
        try:
            import mongo_store

            urls = mongo_store.get_existing_sakshi_urls()
        except Exception as exc:  # noqa: BLE001 - collector must work offline in tests
            logger.warning("Could not load existing Sakshi URLs from Mongo: %s", exc)
            urls = set()

    collector = SakshiCollector(
        existing_urls=urls,
        request_delay=request_delay,
        max_articles=max_articles,
    )
    articles = collector.collect()
    if collector_out is not None:
        collector_out.append(collector)
    return articles


def get_output_path() -> Path:
    return sakshi_config.SAKSHI_OUTPUT_FILE


def save_json(
    articles: list[dict[str, Any]],
    output_path: Path | None = None,
    *,
    filter_stats: dict[str, Any] | None = None,
) -> Path:
    import json

    path = output_path or get_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collector": "Sakshi News Collector",
        "source": sakshi_config.SAKSHI_TAG_URL,
        "source_name": "sakshi",
        "total_articles": len(articles),
        "filter_stats": filter_stats or {},
        "articles": articles,
    }
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %s Sakshi articles to %s", len(articles), path)
    return path


def run() -> Path:
    """Collect Sakshi articles and write the JSON envelope used by the analyzer."""
    started = time.perf_counter()
    holders: list[SakshiCollector] = []
    articles = collect_sakshi_articles(collector_out=holders)
    filter_stats = holders[0].filter_stats if holders else {}
    path = save_json(articles, filter_stats=filter_stats)
    duration = time.perf_counter() - started
    logger.info(
        "Sakshi collector duration=%.2fs | fetched=%s | accepted=%s | rejected=%s",
        duration,
        filter_stats.get("fetched", 0),
        filter_stats.get("accepted", 0),
        filter_stats.get("rejected", 0),
    )
    return path
