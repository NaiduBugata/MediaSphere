"""Sakshi.com Narasaraopet tag-page collector (no scheduling / no Mongo writes)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from collectors.base.base_collector import BaseCollector
from collectors.sakshi import config as sakshi_config
from collectors.sakshi.constituency_validator import (
    ConstituencyValidator,
    get_validator,
)
from pipeline.retry import is_transient, retry_call

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


def _is_skip_url(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in sakshi_config.SKIP_URL_SUBSTRINGS)


def _is_article_url(url: str) -> bool:
    if not url or _is_skip_url(url):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower()
    if "sakshi.com" not in host:
        return False
    path = parsed.path or ""
    # Prefer news paths; allow numeric id paths common on Sakshi.
    if "/tags/" in path or "/category/" in path or path.rstrip("/") in ("", "/"):
        return False
    if any(
        x in path.lower()
        for x in (
            "/news/",
            "/telugu-news/",
            "/andhra-pradesh/",
            "/ap/",
            "/guntur/",
            "/article/",
            "/politics/",
            "/crime/",
        )
    ):
        return True
    # Fallback: long slug paths that look like articles
    slug = path.strip("/").split("/")[-1]
    return bool(slug) and len(slug) > 12 and not slug.endswith((".jpg", ".png", ".gif", ".mp4"))


def _load_url_priority_keywords() -> list[str]:
    """Location keywords used to rank tag-page links (from location dictionary)."""
    fallback = ["narasaraopet", "నరసరావుపేట", "palnadu", "పల్నాడు"]
    try:
        import json

        path = sakshi_config.LOCATION_DICTIONARY_PATH
        if not path.exists():
            return fallback
        data = json.loads(path.read_text(encoding="utf-8"))
        keywords: list[str] = []
        for key in ("primary_keywords", "assembly_segments", "mandals", "villages", "district_aliases"):
            for item in data.get(key) or []:
                if isinstance(item, str) and item.strip():
                    keywords.append(item.strip())
        return keywords or fallback
    except Exception:  # noqa: BLE001
        return fallback


def _url_has_location_keyword(url: str, anchor_text: str, keywords: list[str]) -> bool:
    """
    Match location keywords in URL/anchor with hyphen/slash/word boundaries.

    Plain substring matching is unsafe: short mandals like ``Ipur`` would match
    inside ``jaipur``.
    """
    combined = f"{url} {anchor_text}"
    haystack = combined.lower()
    for keyword in keywords:
        if not keyword or not str(keyword).strip():
            continue
        # Telugu / non-ASCII: require exact substring on original text
        if any(ord(ch) > 127 for ch in keyword):
            if keyword in combined:
                return True
            continue

        token = keyword.lower().strip()
        compact = re.sub(r"[\s_-]+", "", token)
        # Skip very short tokens for URL ranking (too many false positives)
        if len(compact) < 5:
            continue
        # Bound by non-letter edges so "ipur" does not match "jaipur"
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack):
            return True
        if " " in token or "-" in token:
            if compact and re.search(rf"(?<![a-z0-9]){re.escape(compact)}(?![a-z0-9])", haystack.replace("-", "").replace("_", "")):
                return True
        elif compact and re.search(rf"(?<![a-z0-9]){re.escape(compact)}(?![a-z0-9])", haystack.replace("-", "").replace("_", "")):
            return True
    return False


def _is_section_hub_url(url: str) -> bool:
    """Reject district/section hub pages that are not article detail URLs."""
    path = (urlparse(url).path or "").strip("/")
    if not path:
        return True
    parts = path.split("/")
    # e.g. andhra-pradesh/palnadu or andhra-pradesh/amaravati
    if len(parts) <= 2 and not re.search(r"\d{5,}", parts[-1]):
        return True
    slug = parts[-1]
    # Real Sakshi articles usually have long slugs and/or numeric ids
    if len(slug) < 20 and not re.search(r"\d{5,}", slug):
        return True
    return False


def _link_priority(url: str, anchor_text: str = "", keywords: list[str] | None = None) -> int:
    """
    Higher score = fetch earlier.

    Sakshi tag pages embed homepage/sidebar noise ahead of tagged stories.
    Constituency location tokens in the URL/anchor rank highest; non-local
    sections (sports/national/…) rank lowest unless they carry a location token.
    """
    keywords = keywords or _load_url_priority_keywords()
    path = (urlparse(url).path or "").lower()
    has_location = _url_has_location_keyword(url, anchor_text, keywords)

    if has_location:
        return 100
    if any(marker in path for marker in sakshi_config.NON_LOCAL_URL_PATH_MARKERS):
        return 0
    if any(x in path for x in ("/andhra-pradesh/", "/politics/", "/crime/", "/guntur/", "/palnadu/")):
        return 40
    if "/telugu-news/" in path or "/news/" in path:
        return 20
    return 10


def _stable_article_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.replace("/", "_") if path else "unknown"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "", slug)[:80] or "article"
    return f"{cleaned}_{digest}"


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    # ISO-ish
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    # Common newspaper formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%B %d, %Y",
        "%d %b %Y",
    ):
        try:
            dt = datetime.strptime(text[:26], fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    return ""


def _text_or_empty(node) -> str:
    if not node:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


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
            # Skip clear non-local noise unless URL carries a location keyword.
            if priority <= 0:
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

        soup = BeautifulSoup(html, "lxml")
        title = _text_or_empty(soup.select_one(sakshi_config.SAKSHI_TITLE_SELECTOR))
        if not title:
            title = _meta_content(soup, "og:title") or _text_or_empty(soup.title)

        body_node = soup.select_one(sakshi_config.SAKSHI_ARTICLE_BODY_SELECTOR)
        paragraphs: list[str] = []
        if body_node:
            paragraphs = [
                " ".join(p.get_text(" ", strip=True).split())
                for p in body_node.find_all("p")
                if p.get_text(strip=True)
            ]
        if not paragraphs:
            paragraphs = [
                " ".join(p.get_text(" ", strip=True).split())
                for p in soup.find_all("p")
                if p.get_text(strip=True) and len(p.get_text(strip=True)) > 40
            ]

        content = "\n\n".join(paragraphs).strip()
        if not title or len(content) < 80:
            logger.warning("Article missing title/body; skipping %s", url)
            return None

        published = (
            _parse_datetime(_meta_content(soup, "article:published_time", "publish-date", "date"))
            or _parse_datetime(_meta_content(soup, "og:updated_time"))
        )
        time_tag = soup.find("time")
        if not published and time_tag:
            published = _parse_datetime(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))

        canonical = ""
        link = soup.find("link", attrs={"rel": "canonical"})
        if link and link.get("href"):
            canonical = str(link["href"]).strip()

        breadcrumbs = [
            " ".join(li.get_text(" ", strip=True).split())
            for li in soup.select("nav.breadcrumb li, .breadcrumb li, ol.breadcrumb li")
            if li.get_text(strip=True)
        ]

        tags = [
            " ".join(a.get_text(" ", strip=True).split())
            for a in soup.select("a[rel='tag'], .tags a, .story-tags a")
            if a.get_text(strip=True)
        ]

        author = _meta_content(soup, "article:author", "author") or _text_or_empty(
            soup.select_one(".author, .byline, span.author-name")
        )
        category = _meta_content(soup, "article:section") or (breadcrumbs[-2] if len(breadcrumbs) >= 2 else "")
        summary = _meta_content(soup, "og:description", "description")
        thumbnail = _meta_content(soup, "og:image")

        return {
            "url": canonical or url,
            "title": title,
            "content": content,
            "summary": summary,
            "author": author,
            "category": category,
            "tags": tags,
            "breadcrumb": breadcrumbs,
            "thumbnail": thumbnail,
            "description": summary,
            "published_at": published,
            "og_description": summary,
        }

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        content = (raw.get("content") or "").strip()
        published = raw.get("published_at") or datetime.now(timezone.utc).isoformat()
        article_id = _stable_article_id(url)
        validation = raw.get("_constituency_validation") or {}

        return {
            "id": article_id,
            "source": "sakshi",
            "source_type": "newspaper",
            "title": title,
            "content": content,
            "article": content,
            "summary": raw.get("summary") or "",
            "published_at": published,
            "created_on": published,
            "author": raw.get("author") or "",
            "category": raw.get("category") or "",
            "subcategory": "",
            "tags": raw.get("tags") or [],
            "keywords": [],
            "entities": [],
            "location": {},
            "thumbnail": raw.get("thumbnail") or "",
            "description": raw.get("description") or "",
            "source_url": url,
            "url": url,
            "language": "te",
            "channel": "Sakshi",
            "constituency_score": validation.get("score"),
            "constituency_match_reason": validation.get("reason"),
        }

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
