"""Legacy re-export — canonical validator lives in ``sources.base``."""
# ruff: noqa: F401

from sources.base.constituency_validator import (
    ConstituencyValidator,
    ValidationResult,
    _find_matches,
    _normalize_for_match,
    build_searchable_text,
    filter_articles_by_constituency,
    get_validator,
)

__all__ = [
    "ConstituencyValidator",
    "ValidationResult",
    "_find_matches",
    "_normalize_for_match",
    "build_searchable_text",
    "filter_articles_by_constituency",
    "get_validator",
]
