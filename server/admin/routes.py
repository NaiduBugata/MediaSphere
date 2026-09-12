"""Flask routes for /api/admin/* — auth required on all endpoints."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from admin import auth
from admin import fetch_service as fetch_ops

logger = logging.getLogger("admin.routes")

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _unauthorized(message: str = "Unauthorized"):
    return jsonify({"error": message, "status": "unauthorized"}), 401


def _require_admin():
    header = request.headers.get("Authorization") or request.headers.get("X-Admin-Token")
    if not auth.verify_session_token(header):
        return False
    return True


@admin_bp.route("/auth/login", methods=["POST"])
def admin_login():
    if not auth.is_admin_auth_configured():
        return (
            jsonify(
                {
                    "error": "Admin auth is not configured. Set ADMIN_PASSWORD or PIPELINE_ADMIN_TOKEN.",
                    "status": "disabled",
                }
            ),
            503,
        )
    payload = request.get_json(silent=True) or {}
    password = payload.get("password") or payload.get("token") or ""
    if not auth.verify_password(password):
        return jsonify({"error": "Invalid credentials", "status": "forbidden"}), 403
    session = auth.issue_session_token()
    return jsonify({"status": "ok", **session})


@admin_bp.route("/auth/logout", methods=["POST"])
def admin_logout():
    # Stateless tokens — client discards. Endpoint exists for UX completeness.
    return jsonify({"status": "ok"})


@admin_bp.route("/auth/me", methods=["GET"])
def admin_me():
    if not _require_admin():
        return _unauthorized()
    return jsonify({"status": "ok", "role": "admin"})


@admin_bp.route("/fetch/status", methods=["GET"])
def fetch_status():
    if not _require_admin():
        return _unauthorized()
    try:
        return jsonify(fetch_ops.build_admin_status())
    except Exception as exc:
        logger.exception("admin fetch status failed: %s", exc)
        return jsonify({"error": "unavailable", "headline": "unknown"}), 500


@admin_bp.route("/fetch/trigger", methods=["POST"])
def fetch_trigger():
    if not _require_admin():
        return _unauthorized()
    try:
        result = fetch_ops.trigger_fetch(trigger="manual")
        code = 202 if result.get("accepted") else 409
        return jsonify(result), code
    except Exception as exc:
        logger.exception("admin fetch trigger failed: %s", exc)
        return jsonify({"accepted": False, "error": str(exc)[:200]}), 500


@admin_bp.route("/fetch/retry/<run_id>", methods=["POST"])
def fetch_retry(run_id: str):
    if not _require_admin():
        return _unauthorized()
    parent = fetch_ops.get_run(run_id)
    if not parent:
        return jsonify({"error": "Run not found"}), 404
    try:
        result = fetch_ops.trigger_fetch(trigger="retry", parent_run_id=run_id)
        code = 202 if result.get("accepted") else 409
        return jsonify(result), code
    except Exception as exc:
        logger.exception("admin fetch retry failed: %s", exc)
        return jsonify({"accepted": False, "error": str(exc)[:200]}), 500


@admin_bp.route("/fetch/history", methods=["GET"])
def fetch_history():
    if not _require_admin():
        return _unauthorized()
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        limit = 50
    rows = fetch_ops.list_history(
        limit=limit,
        status=request.args.get("status"),
        trigger=request.args.get("trigger"),
        q=request.args.get("q"),
    )
    return jsonify({"runs": rows, "count": len(rows), "stats": fetch_ops.history_stats()})


@admin_bp.route("/fetch/<run_id>", methods=["GET"])
def fetch_detail(run_id: str):
    if not _require_admin():
        return _unauthorized()
    row = fetch_ops.get_run(run_id)
    if not row:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(row)


@admin_bp.route("/scheduler/status", methods=["GET"])
def scheduler_status():
    if not _require_admin():
        return _unauthorized()
    status = fetch_ops.build_admin_status()
    return jsonify(
        {
            "scheduler": status.get("scheduler"),
            "next_run": status.get("next_run"),
            "last_success": status.get("last_success"),
            "interval_hours": status.get("interval_hours"),
            "delay_tolerance_minutes": status.get("delay_tolerance_minutes"),
            "scheduler_delayed": status.get("scheduler_delayed"),
            "delay_seconds": status.get("delay_seconds"),
            "pipeline_on_api": status.get("pipeline_on_api"),
            "headline": status.get("headline"),
        }
    )


@admin_bp.route("/health", methods=["GET"])
def admin_health():
    if not _require_admin():
        return _unauthorized()
    return jsonify(fetch_ops.build_health_check())
