"""Input validation helpers."""

from __future__ import annotations


def is_non_empty_string(value) -> bool:
    """Return True if value is a non-empty string after stripping."""
    return isinstance(value, str) and bool(value.strip())


def clamp(value: int | float, min_val: int | float, max_val: int | float) -> int | float:
    """Clamp value between min_val and max_val."""
    return max(min_val, min(value, max_val))
