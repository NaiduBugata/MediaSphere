import csv
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config import (
    API_BACKOFF_SECONDS,
    API_BASE_URL,
    API_MAX_RETRIES,
    API_PER_PAGE,
    API_TAG_ID,
    API_TIMEOUT_SECONDS,
    CSV_ENCODING,
    CSV_PATH,
    LOOKBACK_HOURS,
    OUTPUT_ENCODING,
    REQUEST_HEADERS,
)


logger = logging.getLogger("lokal_news_collector")


class LokalNewsCollector:
    def __init__(self, csv_path: Path = CSV_PATH) -> None:
        self.csv_path = csv_path
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def fetch_latest_articles(self) -> List[Dict[str, str]]:
        articles: List[Dict[str, str]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        page = 1

        while True:
            payload = self._fetch_page(page)
            if not payload:
                break
            for item in payload:
                published_at = self._parse_datetime(item.get("date_gmt") or item.get("date"))
                if published_at is None:
                    continue
                if published_at < cutoff:
                    return articles
                title = self._clean_text(item.get("title", {}).get("rendered") or item.get("title") or "")
                content = self._clean_text(item.get("content", {}).get("rendered") or item.get("content") or "")
                article_id = str(item.get("id") or "").strip()
                if not title and not content:
                    continue
                if self._is_duplicate(articles, article_id=article_id, title=title, content=content):
                    continue
                articles.append({
                    "id": article_id,
                    "title": title,
                    "date": published_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "content": content,
                })
            if len(payload) < API_PER_PAGE:
                break
            page += 1

        return articles

    def save_csv(self, articles: List[Dict[str, str]]) -> Path:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self.csv_path.open("w", encoding=CSV_ENCODING, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "title", "date", "content"])
            writer.writeheader()
            for row in articles:
                writer.writerow(row)
        return self.csv_path

    def run(self) -> Path:
        articles = self.fetch_latest_articles()
        return self.save_csv(articles)

    def _fetch_page(self, page: int) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"per_page": API_PER_PAGE, "page": page, "context": "embed"}
        if API_TAG_ID:
            params["tags"] = API_TAG_ID
        for attempt in range(1, API_MAX_RETRIES + 1):
            try:
                response = self.session.get(API_BASE_URL, params=params, timeout=API_TIMEOUT_SECONDS)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                logger.warning("Fetch attempt %s failed for page %s: %s", attempt, page, exc)
                if attempt >= API_MAX_RETRIES:
                    return []
                time.sleep(API_BACKOFF_SECONDS * attempt)
        return []

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    def _clean_text(self, value: Any) -> str:
        text = "" if value is None else str(value)
        text = text.replace("\xa0", " ")
        text = " ".join(text.split())
        return text

    def _is_duplicate(self, articles: List[Dict[str, str]], article_id: str = "", title: str = "", content: str = "") -> bool:
        for item in articles:
            if article_id and item.get("id") == article_id:
                return True
            if title and item.get("title") == title:
                return True
            if content and item.get("content") == content:
                return True
        return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    collector = LokalNewsCollector()
    csv_path = collector.run()
    logger.info("Updated CSV: %s", csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
