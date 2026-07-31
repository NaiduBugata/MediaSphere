"""Unit tests for the notification framework."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVER_DIR = Path(__file__).resolve().parents[2]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

os.environ.setdefault("WHATSAPP_WEBHOOK_ENABLED", "true")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify")
os.environ.setdefault("PIPELINE_ON_API", "false")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("EMAIL_ENABLED", "false")
os.environ.setdefault("WHATSAPP_ENABLED", "false")


class FormatterTests(unittest.TestCase):
    def test_truncate(self) -> None:
        from notifications.formatter import truncate

        self.assertEqual(truncate("short"), "short")
        self.assertTrue(truncate("x" * 5000).endswith("…"))
        self.assertLessEqual(len(truncate("x" * 5000)), 3500)

    def test_article_template_variables_order(self) -> None:
        from notifications.formatter import article_template_variables

        vars_ = article_template_variables(
            {
                "source": "sakshi",
                "category": "Infrastructure",
                "sentiment": "Negative",
                "title": "Road damaged",
                "summary": "Residents demand repairs",
                "created_on": "2026-07-20T10:00:00+05:30",
                "source_url": "https://example.com/a",
            }
        )
        self.assertEqual(vars_[0], "Sakshi")
        self.assertEqual(vars_[1], "Infrastructure")
        self.assertEqual(vars_[3], "Road damaged")
        self.assertIn("example.com", vars_[6])


class RetryTests(unittest.TestCase):
    def test_retries_then_succeeds(self) -> None:
        from notifications.exceptions import RetryableChannelError
        from notifications.retry import retry_call

        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RetryableChannelError("temp", status_code=503)
            return "ok"

        with patch("notifications.retry.time.sleep"):
            result, attempts = retry_call(flaky, label="test", max_retries=4, base_seconds=0.01)
        self.assertEqual(result, "ok")
        self.assertEqual(attempts, 3)

    def test_exhausts_retries(self) -> None:
        from notifications.exceptions import RetryableChannelError
        from notifications.retry import retry_call

        def always_fail() -> str:
            raise RetryableChannelError("down", status_code=429)

        with patch("notifications.retry.time.sleep"):
            with self.assertRaises(RetryableChannelError):
                retry_call(always_fail, label="test", max_retries=3, base_seconds=0.01)


class TemplateTests(unittest.TestCase):
    def test_article_alert_contains_sections(self) -> None:
        from notifications.templates import article_alert

        text = article_alert.build_text(
            {
                "title": "Test headline",
                "summary": "Summary here",
                "source": "lokal",
                "category": "Crime",
                "sentiment": "Negative",
                "source_url": "https://x.test/1",
                "location": {"mandal": "Narasaraopet"},
            }
        )
        self.assertIn("NEW NEWS DETECTED", text)
        self.assertIn("Test headline", text)
        self.assertIn("Lokal", text)

    def test_critical_and_failure_templates(self) -> None:
        from notifications.templates import critical_issue, error_alert

        crit = critical_issue.build_text(
            {
                "problem": "No water",
                "severity": "High",
                "source": "sakshi",
                "location": {"village": "Ipur"},
            }
        )
        self.assertIn("CRITICAL ISSUE", crit)
        fail = error_alert.build_text(module="mongo", reason="timeout")
        self.assertIn("PIPELINE FAILURE", fail)
        self.assertIn("mongo", fail)


class WhatsAppChannelTests(unittest.TestCase):
    def test_disabled_skips(self) -> None:
        from notifications.channels.whatsapp_channel import WhatsAppChannel
        from notifications.models import NotificationPayload, NotificationType

        channel = WhatsAppChannel()
        with patch("notifications.channels.whatsapp_channel.config") as cfg:
            cfg.WHATSAPP_ENABLED = False
            cfg.WHATSAPP_ACCESS_TOKEN = ""
            cfg.WHATSAPP_PHONE_NUMBER_ID = ""
            cfg.WHATSAPP_RECIPIENTS = []
            result = channel.send(
                NotificationPayload(
                    notification_type=NotificationType.CUSTOM,
                    subject="t",
                    text_body="hello",
                )
            )
        self.assertTrue(result.skipped)

    def test_template_send_mocked(self) -> None:
        from notifications.channels.whatsapp_channel import WhatsAppChannel
        from notifications.models import NotificationPayload, NotificationType

        channel = WhatsAppChannel()
        mock_resp = {"messages": [{"id": "wamid.TEST"}]}

        with patch(
            "whatsapp.send_service.send_template_message", return_value=mock_resp
        ) as send_tmpl, patch("whatsapp.send_service.send_text_message") as send_text, patch(
            "notifications.channels.whatsapp_channel.config"
        ) as cfg:
            cfg.WHATSAPP_USE_TEMPLATES = True
            cfg.WHATSAPP_TEMPLATE_LANGUAGE = "en"
            cfg.NOTIFICATION_MAX_RETRIES = 2
            cfg.WHATSAPP_RECIPIENTS = ["919999999999"]

            payload = NotificationPayload(
                notification_type=NotificationType.ARTICLE_ALERT,
                subject="alert",
                text_body="body text",
                template_name="mediasphere_article_alert",
                template_variables=[
                    "Sakshi",
                    "News",
                    "Neutral",
                    "Title",
                    "Sum",
                    "20 Jul 2026",
                    "https://x",
                ],
                recipients_whatsapp=["919999999999"],
            )
            with patch.object(WhatsAppChannel, "is_enabled", return_value=True):
                result = channel.send(payload)

        self.assertTrue(result.success)
        self.assertEqual(result.message_id, "wamid.TEST")
        send_tmpl.assert_called_once()
        send_text.assert_not_called()


class EmailChannelTests(unittest.TestCase):
    def test_incremental_delegates_to_reports(self) -> None:
        from notifications.channels.email_channel import EmailChannel
        from notifications.models import NotificationPayload, NotificationType

        channel = EmailChannel()
        with patch.object(EmailChannel, "is_enabled", return_value=True), patch(
            "reports.incremental.send_incremental_report",
            return_value={
                "status": "sent",
                "sent": 1,
                "failed": 0,
                "batch_id": "abc",
                "recipients": ["a@b.c"],
            },
        ) as incr:
            result = channel.send(
                NotificationPayload(
                    notification_type=NotificationType.ARTICLE_ALERT,
                    subject="x",
                    text_body="y",
                    email_incremental=True,
                )
            )
        self.assertTrue(result.success)
        self.assertEqual(result.message_id, "abc")
        incr.assert_called_once()


class ManagerTests(unittest.TestCase):
    def test_dispatches_only_requested_channels(self) -> None:
        from notifications.manager import NotificationManager
        from notifications.models import ChannelResult

        email = MagicMock()
        email.name = "email"
        email.is_enabled.return_value = True
        email.send.return_value = ChannelResult(channel="email", success=True)

        wa = MagicMock()
        wa.name = "whatsapp"
        wa.is_enabled.return_value = True
        wa.send.return_value = ChannelResult(channel="whatsapp", success=True)

        mgr = NotificationManager(channels=[email, wa])
        result = mgr.notify_custom(subject="s", text_body="t", channels=["whatsapp"], async_=False)
        self.assertEqual(result["status"], "ok")
        wa.send.assert_called_once()
        email.send.assert_not_called()

    def test_notify_new_article_pending_sync(self) -> None:
        from notifications.manager import NotificationManager
        from notifications.models import ChannelResult

        email = MagicMock()
        email.name = "email"
        email.is_enabled.return_value = False
        email.send.return_value = ChannelResult(
            channel="email", success=True, skipped=True, skip_reason="email_disabled"
        )

        wa = MagicMock()
        wa.name = "whatsapp"
        wa.is_enabled.return_value = False
        wa.send.return_value = ChannelResult(
            channel="whatsapp", success=True, skipped=True, skip_reason="disabled"
        )

        mgr = NotificationManager(channels=[email, wa])
        result = mgr.notify_new_article(async_=False)
        self.assertEqual(result["status"], "ok")
        email.send.assert_called_once()
        wa.send.assert_called_once()


class UtilsCriticalTests(unittest.TestCase):
    def test_is_critical(self) -> None:
        from notifications.utils import is_critical_article

        self.assertTrue(is_critical_article({"sentiment": "Negative", "severity": "High"}))
        self.assertFalse(is_critical_article({"sentiment": "Negative", "severity": "Low"}))
        self.assertTrue(
            is_critical_article({"sentiment": "Problem", "problem": {"priority": "High"}})
        )


class SendTemplateServiceTests(unittest.TestCase):
    def test_send_template_message_posts_graph(self) -> None:
        from whatsapp.send_service import send_template_message

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.1"}]}

        with patch("whatsapp.send_service.config") as cfg, patch(
            "whatsapp.send_service.requests.post", return_value=mock_response
        ) as post:
            cfg.WHATSAPP_ACCESS_TOKEN = "tok"
            cfg.messages_endpoint.return_value = "https://graph.facebook.com/v25.0/1/messages"
            data = send_template_message(
                "919876543210",
                "mediasphere_article_alert",
                language="en",
                body_parameters=["a", "b"],
            )
        self.assertEqual(data["messages"][0]["id"], "wamid.1")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["type"], "template")
        self.assertEqual(body["template"]["name"], "mediasphere_article_alert")


if __name__ == "__main__":
    unittest.main()
