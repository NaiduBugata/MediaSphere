"""Environment variable parsing helpers used across MediaSphere."""

from __future__ import annotations

import os


def _truthy(name: str, default: str = "false") -> bool:
    """Return True if the named env var is a truthy string."""
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    """Return a float from the named env var, or the default."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    """Return an int from the named env var, or the default."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)
