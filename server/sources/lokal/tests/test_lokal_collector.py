"""Unit tests for the Lokal collector modules (pure functions, no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[3]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from sources.lokal.api import build_page_url  # noqa: E402
from sources.lokal.normalizer import (  # noqa: E402
    build_article_url,
    normalize_article,
    remove_duplicates,
)
from sources.lokal.parser import parse_post_date  # noqa: E402


class ParsePostDateTests(unittest.TestCase):
    def test_parses_iso_with_zulu(self) -> None:
        parsed = parse_post_date("2026-07-10T08:30:00Z")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_parses_iso_with_offset(self) -> None:
        parsed = parse_post_date("2026-07-10T08:30:00+05:30")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.hour, 3)  # converted to UTC

    def test_rejects_invalid(self) -> None:
        self.assertIsNone(parse_post_date(None))
        self.assertIsNone(parse_post_date(""))
        self.assertIsNone(parse_post_date("not-a-date"))


class BuildUrlTests(unittest.TestCase):
    def test_page_url_contains_query_params(self) -> None:
        url = build_page_url(3)
        self.assertIn("page=3", url)
        self.assertIn("tag_id=", url)
        self.assertIn("page_size=", url)

    def test_article_url_prefers_custom_link(self) -> None:
        self.assertEqual(
            build_article_url({"custom_link": "https://example.com/x", "id": 5}),
            "https://example.com/x",
        )

    def test_article_url_from_slug_and_id(self) -> None:
        url = build_article_url({"slug": "my-story", "id": 42})
        self.assertTrue(url.endswith("/my-story-42"))

    def test_article_url_fallback_post_id(self) -> None:
        url = build_article_url({"id": 42})
        self.assertTrue(url.endswith("/post/42"))


class NormalizeTests(unittest.TestCase):
    def test_normalizes_valid_post(self) -> None:
        post = {"id": 1, "title": "T", "content": "C", "created_on": "2026-07-10T08:30:00Z"}
        article = normalize_article(post)
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article["id"], 1)
        self.assertEqual(article["title"], "T")
        self.assertEqual(article["raw"], post)

    def test_skips_post_without_id_or_date(self) -> None:
        self.assertIsNone(normalize_article({"title": "no id", "created_on": "2026-07-10"}))
        self.assertIsNone(normalize_article({"id": 1, "title": "no date"}))


class RemoveDuplicatesTests(unittest.TestCase):
    def test_keeps_newest_by_id(self) -> None:
        older = {"id": 1, "title": "old", "created_on": "2026-07-09T00:00:00Z"}
        newer = {"id": 1, "title": "new", "created_on": "2026-07-10T00:00:00Z"}
        unique = {"id": 2, "title": "other", "created_on": "2026-07-10T00:00:00Z"}
        deduped, removed = remove_duplicates([older, newer, unique])
        self.assertEqual(removed, 1)
        self.assertEqual(len(deduped), 2)
        kept = next(a for a in deduped if a["id"] == 1)
        self.assertEqual(kept["title"], "new")


if __name__ == "__main__":
    unittest.main()
