"""Tests for production pipeline reliability hardening."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
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

from api_server import app  # noqa: E402
import pipeline_config  # noqa: E402
import pipeline_scheduler  # noqa: E402
import pipeline_state  # noqa: E402
import retry_utils  # noqa: E402


class RetryUtilsTests(unittest.TestCase):
    def test_retry_call_succeeds_after_transient(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("temporary")
            return "ok"

        self.assertEqual(retry_utils.retry_call(flaky, retries=3, base_delay=0.01), "ok")
        self.assertEqual(calls["n"], 3)

    def test_retry_call_raises_permanent(self) -> None:
        def bad() -> None:
            raise ValueError("invalid data")

        with self.assertRaises(ValueError):
            retry_utils.retry_call(bad, retries=3, base_delay=0.01)


class PipelineConfigTests(unittest.TestCase):
    def test_validate_requires_mongo_and_groq(self) -> None:
        with patch("pipeline_config.discover_groq_keys", return_value=[]), patch(
            "pipeline_config.PIPELINE_INTERVAL_HOURS", 1.0
        ), patch("os.getenv") as getenv:

            def _getenv(name, default=""):
                if name == "MONGODB_URI":
                    return ""
                if name == "WEB_CONCURRENCY":
                    return None
                if name == "GUNICORN_WORKERS":
                    return None
                return default

            getenv.side_effect = _getenv
            result = pipeline_config.validate_for_scheduler()
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("MONGODB_URI", joined)
        self.assertIn("GROQ", joined)


class PipelineLockTests(unittest.TestCase):
    def test_lock_held_returns_none(self) -> None:
        from pymongo.errors import DuplicateKeyError

        coll = MagicMock()
        coll.find_one_and_update.return_value = None
        coll.insert_one.side_effect = DuplicateKeyError("lock held")

        with patch("pipeline_state.lock_collection", return_value=coll), patch(
            "pipeline_state.ensure_indexes"
        ), patch("pipeline_state.retry_call", side_effect=lambda fn, **kw: fn()):
            owner = pipeline_state.acquire_lock(owner="me")
        self.assertIsNone(owner)

    def test_stale_lock_can_be_acquired(self) -> None:
        coll = MagicMock()
        coll.find_one_and_update.return_value = {"owner": "me"}
        with patch("pipeline_state.lock_collection", return_value=coll), patch(
            "pipeline_state.ensure_indexes"
        ), patch("pipeline_state.retry_call", side_effect=lambda fn, **kw: fn()):
            owner = pipeline_state.acquire_lock(owner="me")
        self.assertEqual(owner, "me")
        self.assertTrue(coll.find_one_and_update.called)


class PipelineSchedulerTests(unittest.TestCase):
    def tearDown(self) -> None:
        try:
            pipeline_scheduler.shutdown()
        except Exception:
            pass

    def test_start_twice_is_idempotent(self) -> None:
        fake_scheduler = MagicMock()
        fake_scheduler.running = True
        fake_job = MagicMock()
        fake_job.next_run_time = datetime.now(timezone.utc) + timedelta(hours=1)
        fake_scheduler.get_job.return_value = fake_job

        with patch("pipeline_scheduler.run_self_test", return_value={"errors": [], "warnings": [], "config_ok": True, "mongo_ok": True, "indexes_ok": True}), patch(
            "pipeline_scheduler.BackgroundScheduler", return_value=fake_scheduler
        ), patch("pipeline_scheduler.pipeline_state.update_state"), patch(
            "pipeline_scheduler.configure_logging"
        ):
            first = pipeline_scheduler.start(run_catch_up=False)
            second = pipeline_scheduler.start(run_catch_up=False)
        self.assertIs(first, second)
        fake_scheduler.start.assert_called_once()
        fake_scheduler.add_job.assert_called_once()

    def test_catch_up_skips_when_last_success_fresh(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        with patch("pipeline_scheduler.pipeline_state.get_state", return_value={"last_success": recent.isoformat()}), patch(
            "pipeline_scheduler.lokal_collector.CHECK_INTERVAL", 3600
        ), patch("pipeline_scheduler._job") as job:
            pipeline_scheduler._catch_up()
        job.assert_not_called()

    def test_catch_up_runs_when_stale(self) -> None:
        stale = datetime.now(timezone.utc) - timedelta(hours=3)
        with patch("pipeline_scheduler.pipeline_state.get_state", return_value={"last_success": stale.isoformat()}), patch(
            "pipeline_scheduler.lokal_collector.CHECK_INTERVAL", 3600
        ), patch("pipeline_scheduler._job") as job:
            pipeline_scheduler._catch_up()
        job.assert_called_once_with(trigger="catch_up")

    def test_failed_cycle_does_not_set_last_success(self) -> None:
        updates: list[dict] = []

        def capture_update(fields):
            updates.append(fields)
            return fields

        with patch("pipeline_scheduler.pipeline_state.acquire_lock", return_value="owner-1"), patch(
            "pipeline_scheduler.pipeline_state.release_lock", return_value=True
        ), patch(
            "pipeline_scheduler.run_combined_cycle",
            return_value=(1, {"inserted": 0, "duplicates": 0, "articles_fetched": 0, "errors": ["boom"], "lokal_processed": 0, "youtube_processed": 0}),
        ), patch("pipeline_scheduler.pipeline_state.update_state", side_effect=capture_update), patch(
            "pipeline_scheduler.pipeline_state.record_history"
        ):
            pipeline_scheduler._job(trigger="interval")

        success_updates = [u for u in updates if "last_success" in u]
        failure_updates = [u for u in updates if "last_failure" in u]
        self.assertEqual(success_updates, [])
        self.assertTrue(failure_updates)

    def test_lock_skip_when_held(self) -> None:
        with patch("pipeline_scheduler.pipeline_state.acquire_lock", return_value=None), patch(
            "pipeline_scheduler.run_combined_cycle"
        ) as cycle:
            pipeline_scheduler._job(trigger="interval")
        cycle.assert_not_called()


class ApiHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_pipeline_health_shape(self) -> None:
        with patch(
            "pipeline_scheduler.health_snapshot",
            return_value={
                "scheduler": "running",
                "last_run": "2026-01-01T00:00:00+00:00",
                "last_success": "2026-01-01T00:00:00+00:00",
                "next_run": "2026-01-01T01:00:00+00:00",
                "status": "success",
                "articles_processed": 10,
                "last_duration_seconds": 12.5,
                "lock": {"held": False},
            },
        ):
            response = self.client.get("/api/pipeline/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["scheduler"], "running")
        self.assertEqual(payload["status"], "healthy")
        self.assertNotIn("MONGODB_URI", str(payload))
        self.assertNotIn("GROQ", str(payload).upper())

    def test_database_health_shape(self) -> None:
        with patch(
            "pipeline_state.ping_mongo",
            return_value={
                "ok": True,
                "latency_ms": 1.2,
                "database": "MediaSphere",
                "articles_collection": "articles",
                "articles_count": 5,
            },
        ):
            response = self.client.get("/api/database/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["database"], "MediaSphere")

    def test_news_cache_control_and_revision(self) -> None:
        with patch("mongo_store.get_collection") as get_col, patch(
            "pipeline_state.get_data_revision", return_value="rev-1"
        ):
            get_col.return_value.find.return_value = []
            response = self.client.get("/api/news")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(response.get_json().get("data_revision"), "rev-1")


class FingerprintTests(unittest.TestCase):
    def test_content_fingerprint_stable(self) -> None:
        import mongo_store

        a = mongo_store._content_fingerprint("lokal", "Hello World", "https://example.com/a")
        b = mongo_store._content_fingerprint("lokal", "  Hello   World  ", "https://example.com/a")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
