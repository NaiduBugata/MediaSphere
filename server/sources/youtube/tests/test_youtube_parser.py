"""Unit tests for YouTube transcript filtering and normalization (no network)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[3]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from sources.youtube.normalizer import normalize_video  # noqa: E402
from sources.youtube.parser import TranscriptCleaner  # noqa: E402


class TranscriptCleanerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cleaner = TranscriptCleaner()

    def test_news_channel_without_non_news_keywords_is_news(self) -> None:
        result = self.cleaner.clean("ఏదో వార్త సమాచారం", "Local update", "TV9 Telugu")
        self.assertTrue(result["is_news"])
        self.assertTrue(result["clean_text"])

    def test_non_news_keyword_in_title_filters_out(self) -> None:
        result = self.cleaner.clean("some transcript", "New movie trailer reaction", "Random Channel")
        self.assertFalse(result["is_news"])
        self.assertEqual(result["clean_text"], "")

    def test_news_indicator_in_transcript_marks_news(self) -> None:
        result = self.cleaner.clean("పోలీస్ అరెస్ట్ ఘటన వివరాలు", "Village report", "Some Channel")
        self.assertTrue(result["is_news"])

    def test_filler_patterns_removed(self) -> None:
        result = self.cleaner.clean(
            "వార్తలు వివరాలు subscribe like and share",
            "News bulletin",
            "TV9",
        )
        self.assertTrue(result["is_news"])
        self.assertNotIn("subscribe", result["clean_text"].lower())


class NormalizeVideoTests(unittest.TestCase):
    def test_maps_transcript_item_to_article(self) -> None:
        item = {
            "video_id": "abc123",
            "title": "T",
            "channel": "TV9",
            "url": "https://www.youtube.com/watch?v=abc123",
            "published_at": "2026-07-10T08:30:00Z",
        }
        article = normalize_video(item, "clean text")
        self.assertEqual(article["id"], "abc123")
        self.assertEqual(article["video_id"], "abc123")
        self.assertEqual(article["content"], "clean text")
        self.assertEqual(article["created_on"], "2026-07-10T08:30:00Z")
        self.assertEqual(article["channel"], "TV9")


if __name__ == "__main__":
    unittest.main()
