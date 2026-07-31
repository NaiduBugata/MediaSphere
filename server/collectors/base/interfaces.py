"""Type definitions and protocols for the collector framework."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CollectorProtocol(Protocol):
    """Protocol that all collectors must satisfy."""

    def fetch_links(self) -> list[str]: ...
    def fetch_article(self, url: str) -> dict[str, Any] | None: ...
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]: ...
    def collect(self) -> list[dict[str, Any]]: ...


class CollectorResult:
    """Standard result from a collector run."""

    def __init__(
        self,
        source: str,
        articles: list[dict[str, Any]],
        *,
        output_path: str | None = None,
        error: str | None = None,
    ) -> None:
        self.source = source
        self.articles = articles
        self.count = len(articles)
        self.output_path = output_path
        self.error = error

    @property
    def success(self) -> bool:
        return self.error is None
