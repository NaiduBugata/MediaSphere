"""Centralized configuration for the daily report feature.

All values are read from environment variables (loaded from .env). No
credentials or environment-specific values are hardcoded here.
"""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_list(name: str) -> list[str]:
    raw = os.getenv(name, "") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---- Scheduler ----
REPORT_ENABLED = _get_bool("REPORT_ENABLED", True)
REPORT_TIMEZONE_NAME = os.getenv("REPORT_TIMEZONE", "Asia/Kolkata")
REPORT_TIMEZONE = ZoneInfo(REPORT_TIMEZONE_NAME)
REPORT_HOUR = _get_int("REPORT_HOUR", 7)
REPORT_MINUTE = _get_int("REPORT_MINUTE", 0)
CONSTITUENCY_NAME = os.getenv("REPORT_CONSTITUENCY", "Narasaraopet")

# ---- Output ----
REPORT_OUTPUT_DIR = BASE_DIR / os.getenv("REPORT_OUTPUT_DIR", "reports_output")

# ---- SMTP ----
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _get_int("SMTP_PORT", 465)
SMTP_USE_SSL = _get_bool("SMTP_USE_SSL", True)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "MediaSphere Intelligence")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
SMTP_MAX_RETRIES = _get_int("SMTP_MAX_RETRIES", 3)
SMTP_RETRY_BACKOFF_SECONDS = _get_int("SMTP_RETRY_BACKOFF_SECONDS", 5)

# ---- Recipients ----
REPORT_RECIPIENTS = _get_list("REPORT_RECIPIENTS")

# ---- Groq (executive summary) ----
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT_SECONDS = _get_int("GROQ_TIMEOUT_SECONDS", 120)


def groq_api_keys() -> list[str]:
    """Collect all configured GROQ_API_KEY_* values."""
    keys = []
    for i in range(1, 11):
        value = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
        if value:
            keys.append(value)
    single = os.getenv("GROQ_API_KEY", "").strip()
    if single:
        keys.append(single)
    return keys


# ---- Branding ----
PRIMARY_COLOR = "#1E3A8A"
SECONDARY_COLOR = "#F8FAFC"
BORDER_COLOR = "#E2E8F0"
TEXT_COLOR = "#1F2937"
MUTED_COLOR = "#6B7280"

# ---- Report limits ----
MAX_ACTION_ITEMS = 10
MAX_POSITIVE_ITEMS = 10
MAX_KEYWORDS = 15
MAX_ENTITIES = 15
TOP_LOCATIONS = 5

CATEGORY_ORDER = [
    "Transport",
    "Employment",
    "Agriculture",
    "Education",
    "Health",
    "Roads",
    "Infrastructure",
    "Politics",
    "Water",
    "Crime",
    "Others",
]


def ensure_output_dir() -> Path:
    """Create and return the report output directory."""
    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_OUTPUT_DIR
