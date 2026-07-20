"""Legacy shim — re-exports from sources.sakshi.validator."""
# ruff: noqa: F401

from sources.sakshi.validator import (
    ConstituencyValidator,
    ValidationResult,
    _find_matches,
    _normalize_for_match,
    build_searchable_text,
    filter_articles_by_constituency,
    get_validator,
)
