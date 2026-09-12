"""Admin authentication — HMAC-signed bearer tokens (no public access)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any


def admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "").strip()


def admin_password() -> str:
    """Prefer ADMIN_PASSWORD; fall back to PIPELINE_ADMIN_TOKEN so one secret works."""
    return (
        os.getenv("ADMIN_PASSWORD", "").strip()
        or os.getenv("PIPELINE_ADMIN_TOKEN", "").strip()
    )


def admin_signing_secret() -> str:
    return (
        os.getenv("ADMIN_SESSION_SECRET", "").strip()
        or admin_password()
        or "mediasphere-admin-dev-insecure"
    )


def is_admin_auth_configured() -> bool:
    return bool(admin_password())


def _sign(payload: str) -> str:
    return hmac.new(
        admin_signing_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_session_token(*, ttl_seconds: int | None = None) -> dict[str, Any]:
    ttl = ttl_seconds or int(os.getenv("ADMIN_SESSION_TTL_SECONDS", "28800"))
    exp = int(time.time()) + max(300, ttl)
    payload = f"admin:{exp}"
    token = f"{payload}.{_sign(payload)}"
    return {"token": token, "expires_at": exp, "token_type": "Bearer"}


def verify_session_token(token: str | None) -> bool:
    if not token or not is_admin_auth_configured():
        return False
    raw = token.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    if "." not in raw:
        return False
    payload, signature = raw.rsplit(".", 1)
    expected = _sign(payload)
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        role, exp_s = payload.split(":", 1)
        if role != "admin":
            return False
        return int(exp_s) >= int(time.time())
    except ValueError:
        return False


def verify_credentials(username: str | None, password: str | None) -> bool:
    """Validate admin username + password.

    If ADMIN_USERNAME is unset, only the password is checked (legacy).
    """
    expected_password = admin_password()
    if not expected_password or password is None:
        return False
    if not hmac.compare_digest(str(password), expected_password):
        return False

    expected_user = admin_username()
    if not expected_user:
        return True
    if username is None:
        return False
    return hmac.compare_digest(str(username).strip().lower(), expected_user.lower())


def verify_password(password: str | None) -> bool:
    """Backward-compatible password-only check."""
    return verify_credentials(admin_username() or None, password)
