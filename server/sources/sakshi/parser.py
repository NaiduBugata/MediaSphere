"""URL heuristics, link ranking, and HTML micro-parsers for Sakshi pages."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from sources.sakshi import config as sakshi_config

logger = logging.getLogger("collectors.sakshi")


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
