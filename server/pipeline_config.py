"""Pipeline scheduler configuration and start-up validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


PIPELINE_ON_API = _truthy("PIPELINE_ON_API", "false")
PIPELINE_CATCHUP_ON_START = _truthy("PIPELINE_CATCHUP_ON_START", "true")
PIPELINE_INTERVAL_HOURS = _float_env("PIPELINE_INTERVAL_HOURS", 1.0)
PIPELINE_LOCK_TTL_SECONDS = max(60, _int_env("PIPELINE_LOCK_TTL_SECONDS", 45 * 60))
PIPELINE_ADMIN_TOKEN = os.getenv("PIPELINE_ADMIN_TOKEN", "").strip()
PIPELINE_STATE_ID = "pipeline"
JOB_ID = "news_pipeline"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def discover_groq_keys() -> list[str]:
    numbered: list[tuple[int, str]] = []
    for env_key, env_value in os.environ.items():
        match = re.fullmatch(r"GROQ_API_KEY_(\d+)", env_key)
        if match and env_value.strip():
            numbered.append((int(match.group(1)), env_value.strip()))
    numbered.sort(key=lambda item: item[0])
    keys = [value for _, value in numbered]
    for alt in ("GROQ_API_KEY", "GROQ_API_KEYS"):
        raw = os.getenv(alt, "").strip()
        if not raw:
            continue
        if "," in raw:
            keys.extend(part.strip() for part in raw.split(",") if part.strip())
        else:
            keys.append(raw)
    # Preserve order, drop empties/dupes
    seen: set[str] = set()
    unique: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def validate_for_scheduler() -> ValidationResult:
    """Fail-fast checks before the in-process scheduler starts."""
    errors: list[str] = []
    warnings: list[str] = []

    if PIPELINE_INTERVAL_HOURS <= 0:
        errors.append("PIPELINE_INTERVAL_HOURS must be > 0")

    if not os.getenv("MONGODB_URI", "").strip():
        errors.append("MONGODB_URI is required when the pipeline scheduler runs")

    if not discover_groq_keys():
        errors.append("At least one GROQ_API_KEY / GROQ_API_KEY_N is required for analysis")

    workers = os.getenv("WEB_CONCURRENCY") or os.getenv("GUNICORN_WORKERS")
    if workers:
        try:
            if int(workers) > 1:
                warnings.append(
                    f"WEB_CONCURRENCY/GUNICORN_WORKERS={workers}: keep gunicorn --workers 1 "
                    "on Render Free; Mongo lock mitigates duplicates but single worker is required."
                )
        except ValueError:
            warnings.append(f"Invalid worker count env value: {workers!r}")

    return ValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))
