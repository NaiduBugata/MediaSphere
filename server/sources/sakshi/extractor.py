"""Field extraction from downloaded Sakshi article HTML."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from sources.sakshi import config as sakshi_config
from sources.sakshi.parser import _meta_content, _parse_datetime, _text_or_empty

logger = logging.getLogger("collectors.sakshi")


def extract_article(html: str, url: str) -> dict[str, Any] | None:
    """
    Stage 2: extract title, body, metadata, breadcrumb, tags, and category.

    Returns the raw article dict, or None when title/body are unusable.
    """
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
