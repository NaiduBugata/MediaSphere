"""Unit tests for Sakshi collector integration (fixture HTML, no live network)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

os.environ.setdefault("WHATSAPP_WEBHOOK_ENABLED", "true")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("PIPELINE_ON_API", "false")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("GROQ_API_KEY_1", "test-key")
os.environ.setdefault("SAKSHI_ENABLED", "true")

from api_server import app  # noqa: E402
from collectors.sakshi.collector import (  # noqa: E402
    PermanentHttpError,
    SakshiCollector,
    _get_html,
    _is_article_url,
)
import mongo_store  # noqa: E402
import pipeline_scheduler  # noqa: E402
import run_all_pipelines  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sakshi"


class SakshiLinkExtractionTests(unittest.TestCase):
    def test_tag_page_filters_and_dedupes(self) -> None:
        html = (FIXTURES / "tag_page.html").read_text(encoding="utf-8")
        collector = SakshiCollector(request_delay=0, max_articles=20, existing_urls=set())
        with patch.object(collector, "session"), patch(
            "collectors.sakshi.collector._get_html", return_value=html
        ):
            links = collector.fetch_links()
        self.assertEqual(len(links), 2)
        self.assertTrue(any("narasaraopet-road-works" in u for u in links))
        self.assertTrue(any("local-school-reopens" in u for u in links))
        self.assertFalse(any("/videos/" in u for u in links))
        self.assertFalse(any("example.com" in u for u in links))

    def test_article_url_heuristics(self) -> None:
        self.assertTrue(
            _is_article_url("https://www.sakshi.com/news/andhra-pradesh/some-long-story-slug-here")
        )
        self.assertFalse(_is_article_url("https://www.sakshi.com/videos/clip"))
        self.assertFalse(_is_article_url("https://www.sakshi.com/tags/narasaraopet"))


class SakshiArticleParseTests(unittest.TestCase):
    def test_fetch_article_and_normalize(self) -> None:
        html = (FIXTURES / "article_page.html").read_text(encoding="utf-8")
        url = "https://www.sakshi.com/news/andhra-pradesh/narasaraopet-road-works-12345"
        collector = SakshiCollector(request_delay=0, existing_urls=set())
        with patch("collectors.sakshi.collector._get_html", return_value=html):
            raw = collector.fetch_article(url)
        self.assertIsNotNone(raw)
        assert raw is not None
        self.assertIn("రోడ్డు", raw["title"])
        self.assertIn("రోడ్డు పనులు", raw["content"])
        self.assertTrue(raw["published_at"])

        normalized = collector.normalize(raw)
        self.assertEqual(normalized["source"], "sakshi")
        self.assertEqual(normalized["source_type"], "newspaper")
        self.assertEqual(normalized["language"], "te")
        self.assertEqual(normalized["channel"], "Sakshi")
        self.assertEqual(normalized["source_url"], url)
        self.assertTrue(normalized["id"])
        self.assertEqual(normalized["content"], normalized["article"])
        self.assertEqual(normalized["created_on"], normalized["published_at"])


class SakshiFingerprintTests(unittest.TestCase):
    def test_fingerprint_sha256_includes_body_and_is_stable(self) -> None:
        a = mongo_store._content_fingerprint(
            "sakshi",
            "Title One",
            body="Body text",
            published_at="2026-07-10T08:30:00+05:30",
        )
        b = mongo_store._content_fingerprint(
            "sakshi",
            "Title One",
            body="Body text",
            published_at="2026-07-10T08:30:00+05:30",
        )
        c = mongo_store._content_fingerprint(
            "sakshi",
            "Title One",
            body="Body text changed",
            published_at="2026-07-10T08:30:00+05:30",
        )
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), 64)

    def test_duplicate_fingerprint_skips_insert(self) -> None:
        from pymongo.errors import DuplicateKeyError

        collection = MagicMock()
        collection.update_one.side_effect = DuplicateKeyError("dup")
        title_map = {
            "Same Title": {
                "post_id": "sakshi_abc123",
                "url": "https://www.sakshi.com/news/x",
                "created_on": "2026-07-10T08:30:00+05:30",
                "content": "body",
                "channel": "Sakshi",
                "author": "",
                "thumbnail": "",
                "tags": [],
            }
        }
        with patch("database.mongo.get_collection", return_value=collection), patch(
            "retry_utils.retry_call", side_effect=lambda fn, **kw: fn()
        ), patch("database.mongo.build_sakshi_postid_map", return_value=title_map):
            stats = mongo_store.upsert_sakshi_articles(
                [{"title": "Same Title", "summary": "body"}],
                Path("dummy.json"),
            )
        self.assertEqual(stats["duplicates"], 1)
        self.assertEqual(stats["inserted"], 0)


class SakshiRetryTests(unittest.TestCase):
    def test_retries_only_transient_status(self) -> None:
        session = MagicMock()
        ok = MagicMock()
        ok.status_code = 200
        ok.text = "<html></html>"
        ok.apparent_encoding = "utf-8"
        transient = MagicMock()
        transient.status_code = 503
        session.get.side_effect = [transient, ok]

        with patch("pipeline.retry.time.sleep"):
            html = _get_html(session, "https://www.sakshi.com/news/example-long-enough")
        self.assertIn("html", html)
        self.assertEqual(session.get.call_count, 2)

    def test_does_not_retry_404(self) -> None:
        session = MagicMock()
        missing = MagicMock()
        missing.status_code = 404
        session.get.return_value = missing
        with self.assertRaises(PermanentHttpError):
            _get_html(session, "https://www.sakshi.com/news/missing-article-page")
        self.assertEqual(session.get.call_count, 1)


class CombinedCycleSakshiTests(unittest.TestCase):
    def test_combined_cycle_invokes_sakshi_when_enabled(self) -> None:
        lokal_stats = {"inserted": 1, "duplicates": 0, "articles_fetched": 1, "total": 1, "errors": []}
        yt_stats = {"inserted": 0, "duplicates": 0, "articles_fetched": 0, "total": 0, "errors": []}
        sakshi_stats = {"inserted": 2, "duplicates": 0, "articles_fetched": 2, "total": 2, "errors": []}

        with patch("pipeline.runner.run_lokal_cycle", return_value=(0, lokal_stats)), patch(
            "pipeline.runner.yt_config.YOUTUBE_ENABLED", False
        ), patch("pipeline.runner.sakshi_config.SAKSHI_ENABLED", True), patch(
            "pipeline.runner.run_sakshi_cycle", return_value=(0, sakshi_stats)
        ) as sakshi_cycle:
            code, stats = run_all_pipelines.run_combined_cycle()

        sakshi_cycle.assert_called_once()
        self.assertEqual(code, 0)
        self.assertEqual(stats["sakshi_processed"], 2)
        self.assertEqual(stats["inserted"], 3)


class HealthAndApiSakshiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_health_snapshot_includes_sakshi_keys(self) -> None:
        with patch(
            "pipeline_scheduler.pipeline_state.get_state",
            return_value={
                "last_run": "2026-07-14T00:00:00+00:00",
                "last_success": "2026-07-14T00:00:00+00:00",
                "status": "success",
                "last_sakshi_run": "2026-07-14T00:00:00+00:00",
                "last_sakshi_articles": 8,
            },
        ), patch("pipeline_scheduler.pipeline_state.get_lock_summary", return_value={"held": False}), patch(
            "pipeline_scheduler.pipeline_state.article_count", return_value=10
        ), patch("pipeline_scheduler.is_running", return_value=True), patch(
            "collectors.config.SAKSHI_ENABLED", True
        ), patch("youtube.config.YOUTUBE_ENABLED", True):
            snap = pipeline_scheduler.health_snapshot()

        self.assertIn("sakshi", snap["sources"])
        self.assertEqual(snap["last_sakshi_articles"], 8)
        self.assertEqual(snap["last_sakshi_run"], "2026-07-14T00:00:00+00:00")
        self.assertEqual(snap["sources"]["sakshi"], "healthy")

    def test_api_source_sakshi_filter(self) -> None:
        docs = [
            {"post_id": "l1", "source": "lokal", "title": "L", "created_on": "2026-07-14T10:00:00+00:00"},
            {
                "post_id": "s1",
                "source": "sakshi",
                "title": "S",
                "created_on": "2026-07-14T11:00:00+00:00",
                "channel": "Sakshi",
            },
        ]
        with patch("mongo_store.get_collection") as get_col, patch(
            "pipeline_state.get_data_revision", return_value="rev"
        ):
            get_col.return_value.find.return_value = docs
            response = self.client.get("/api/news?source=sakshi")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["articles"][0]["source"], "sakshi")


if __name__ == "__main__":
    unittest.main()
