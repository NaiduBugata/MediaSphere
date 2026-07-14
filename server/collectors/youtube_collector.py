"""Adapter wrapping the existing YouTube collector behind BaseCollector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from collectors.base.base_collector import BaseCollector
from youtube import collector as yt_collector


class YouTubeCollectorAdapter(BaseCollector):
    """Thin adapter; production entry remains ``youtube.collector.run()``."""

    def fetch_links(self) -> list[str]:
        path = yt_collector.run()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [a.get("url") for a in payload.get("articles", []) if a.get("url")]

    def fetch_article(self, url: str) -> dict[str, Any] | None:
        return None

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    def collect(self) -> list[dict[str, Any]]:
        path = yt_collector.run()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return list(payload.get("articles") or [])


def run(days: int | None = None) -> Path:
    return yt_collector.run(days=days)
