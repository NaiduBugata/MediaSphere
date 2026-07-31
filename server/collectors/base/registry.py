"""Collector auto-registration and discovery."""

from __future__ import annotations

import logging
from typing import Any

from collectors.base.base_collector import BaseCollector

logger = logging.getLogger("collectors.registry")

_REGISTRY: dict[str, type[BaseCollector]] = {}


def register(name: str):
    """Class decorator to register a collector by source name."""
    def decorator(cls: type[BaseCollector]):
        _REGISTRY[name] = cls
        logger.debug("Registered collector: %s -> %s", name, cls.__name__)
        return cls
    return decorator


def get_collector(name: str) -> type[BaseCollector] | None:
    """Return a registered collector class by name, or None."""
    return _REGISTRY.get(name)


def all_collectors() -> dict[str, type[BaseCollector]]:
    """Return all registered collectors."""
    return dict(_REGISTRY)


def enabled_collectors() -> list[tuple[str, type[BaseCollector]]]:
    """Return collectors that are currently enabled via their config."""
    enabled: list[tuple[str, type[BaseCollector]]] = []
    for name, cls in _REGISTRY.items():
        if hasattr(cls, "is_enabled") and callable(cls.is_enabled):
            if cls.is_enabled():
                enabled.append((name, cls))
        else:
            enabled.append((name, cls))
    return enabled
