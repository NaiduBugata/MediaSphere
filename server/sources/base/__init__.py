"""Base collector framework: ABC, registry, manager, and shared filters."""

from sources.base.base_collector import BaseCollector
from sources.base.constituency_validator import (
    ConstituencyValidator,
    filter_articles_by_constituency,
    get_validator,
)
from sources.base.registry import register, all_collectors, enabled_collectors

__all__ = [
    "BaseCollector",
    "ConstituencyValidator",
    "filter_articles_by_constituency",
    "get_validator",
    "register",
    "all_collectors",
    "enabled_collectors",
]
