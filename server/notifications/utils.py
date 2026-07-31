"""Shared helpers for the notification framework."""

from __future__ import annotations

import re
from typing import Any

_PHONE_RE = re.compile(r"^\d{8,15}$")


def normalize_phone(recipient: str) -> str:
    """Strip formatting and validate E.164-ish digits for WhatsApp Cloud API."""
    cleaned = recipient.strip().lstrip("+").replace(" ", "").replace("-", "")
    if not _PHONE_RE.match(cleaned):
        raise ValueError(f"Invalid WhatsApp recipient: {recipient!r}")
    return cleaned


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def is_critical_article(article: dict[str, Any]) -> bool:
    """True when AI marks Negative/Problem with High severity."""
    sentiment = safe_str(article.get("sentiment")).lower()
    severity = safe_str(article.get("severity")).lower()
    if sentiment in ("negative", "problem") and severity == "high":
        return True
    # Some analyzer outputs put priority on nested problem metadata.
    problem = article.get("problem")
    if isinstance(problem, dict):
        priority = safe_str(problem.get("priority")).lower()
        if sentiment in ("negative", "problem") and priority == "high":
            return True
    return False


def location_label(article: dict[str, Any]) -> str:
    loc = article.get("location")
    if isinstance(loc, dict):
        for key in ("village", "mandal", "town", "district"):
            value = safe_str(loc.get(key))
            if value and value.lower() != "unknown":
                return value
        return "Narasaraopet"
    if isinstance(loc, str) and loc.strip():
        return loc.strip()
    return "Narasaraopet"
