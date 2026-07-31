"""Flask routes for WhatsApp Cloud API webhook verification and events."""

from __future__ import annotations

from flask import Blueprint, Response, request

from . import config
from . import webhook_handler
from .logger import log_event

whatsapp_bp = Blueprint("whatsapp", __name__)


def _client_ip() -> str | None:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr


@whatsapp_bp.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta webhook verification handshake."""
    if not config.WHATSAPP_WEBHOOK_ENABLED:
        return Response("Webhook disabled", status=503, mimetype="text/plain")

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    log_event(
        "info",
        client_ip=_client_ip(),
        headers=dict(request.headers),
        extra={"hub_mode": mode, "verification_attempt": True},
    )

    if (
        mode == "subscribe"
        and token
        and config.WHATSAPP_VERIFY_TOKEN
        and token == config.WHATSAPP_VERIFY_TOKEN
        and challenge is not None
    ):
        log_event(
            "info",
            client_ip=_client_ip(),
            headers=dict(request.headers),
            event_category="webhook",
            event_type="verification_success",
        )
        return Response(str(challenge), status=200, mimetype="text/plain")

    log_event(
        "warning",
        client_ip=_client_ip(),
        headers=dict(request.headers),
        event_category="webhook",
        event_type="verification_failed",
        error="Invalid hub.mode or hub.verify_token",
    )
    return Response("Forbidden", status=403, mimetype="text/plain")


@whatsapp_bp.route("/webhook", methods=["POST"])
def receive_webhook():
    """Receive WhatsApp Cloud API webhook events from Meta."""
    if not config.WHATSAPP_WEBHOOK_ENABLED:
        return Response("Webhook disabled", status=503, mimetype="text/plain")

    client_ip = _client_ip()
    headers = dict(request.headers)

    if not request.data:
        body, status = webhook_handler.process_webhook_post(
            None,
            client_ip=client_ip,
            headers=headers,
        )
        return Response(body, status=status, mimetype="text/plain")

    payload = request.get_json(force=False, silent=True)
    body, status = webhook_handler.process_webhook_post(
        payload,
        client_ip=client_ip,
        headers=headers,
    )
    return Response(body, status=status, mimetype="text/plain")
