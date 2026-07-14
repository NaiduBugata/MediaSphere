"""Abstract base collector for MediaSphere news sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Contract for newspaper / site collectors.

    Implementations must not schedule themselves, sleep for orchestration,
    categorize with AI, or write to MongoDB. Those stages live in runners.
    """

    @abstractmethod
    def fetch_links(self) -> list[str]:
        """Return candidate article URLs from the source index/tag page."""

    @abstractmethod
    def fetch_article(self, url: str) -> dict[str, Any] | None:
        """Download and extract a single article. Return None if unusable."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map raw extraction into MediaSphere collector article shape."""

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        """Fetch links, download new articles, normalize, and return the list."""
