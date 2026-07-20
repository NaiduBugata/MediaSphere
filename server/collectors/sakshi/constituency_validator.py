"""Legacy shim — re-exports from sources.sakshi.validator."""
# ruff: noqa: F401

from sources.sakshi.validator import (
    ConstituencyValidator,
    ValidationResult,
    _find_matches,
    _normalize_for_match,
    build_searchable_text,
    get_validator,
)
