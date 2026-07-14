"""Tests for WhatsApp Cloud API webhook routes."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_DIR = Path(__file__).resolve().parents[2]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("WHATSAPP_WEBHOOK_ENABLED", "true")
os.environ.setdefault("WHATSAPP_WABA_ID", "123456789")

from api_server import app  # noqa: E402


TEXT_MESSAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "987654321",
                        },
                        "contacts": [
                            {
                                "profile": {"name": "Test User"},
                                "wa_id": "919876543210",
                            }
                        ],
                        "messages": [
                            {
                                "from": "919876543210",
                                "id": "wamid.test123",
                                "timestamp": "1710000000",
                                "type": "text",
                                "text": {"body": "Hello MediaSphere"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}

STATUS_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "987654321",
                        },
                        "statuses": [
                            {
                                "id": "wamid.test123",
                                "status": "delivered",
                                "timestamp": "1710000001",
                                "recipient_id": "919876543210",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


class WhatsAppWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_get_verification_success(self) -> None:
        response = self.client.get(
            "/webhook",
            query_string={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "1234567890",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "1234567890")
        self.assertEqual(response.mimetype, "text/plain")

    def test_get_verification_failure(self) -> None:
        response = self.client.get(
            "/webhook",
            query_string={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "1234567890",
            },
        )
        self.assertEqual(response.status_code, 403)

    @patch("whatsapp.webhook_handler.db_service.save_event")
    def test_post_text_message(self, mock_save) -> None:
        response = self.client.post(
            "/webhook",
            data=json.dumps(TEXT_MESSAGE_PAYLOAD),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "EVENT_RECEIVED")
        self.assertTrue(mock_save.called)

    @patch("whatsapp.webhook_handler.db_service.save_event")
    def test_post_status_update(self, mock_save) -> None:
        response = self.client.post(
            "/webhook",
            data=json.dumps(STATUS_PAYLOAD),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "EVENT_RECEIVED")
        self.assertTrue(mock_save.called)

    def test_post_malformed_json(self) -> None:
        response = self.client.post(
            "/webhook",
            data="{not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("whatsapp.webhook_handler.db_service.save_event")
    def test_post_unknown_event_still_accepted(self, mock_save) -> None:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [{"field": "account_update", "value": {}}],
                }
            ],
        }
        response = self.client.post(
            "/webhook",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "EVENT_RECEIVED")
        self.assertTrue(mock_save.called)


if __name__ == "__main__":
    unittest.main()
