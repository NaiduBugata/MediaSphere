"""Base collector framework: ABC, registry, and manager."""

from sources.base.base_collector import BaseCollector
from sources.base.registry import register, all_collectors, enabled_collectors

__all__ = ["BaseCollector", "register", "all_collectors", "enabled_collectors"]
