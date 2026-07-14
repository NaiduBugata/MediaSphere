"""Adapter wrapping the existing Lokal API collector behind BaseCollector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lokal_collector as lokal_module
from collectors.base_collector import BaseCollector


class LokalCollectorAdapter(BaseCollector):
    """Thin adapter; production entry remains ``lokal_collector.run()``."""

    def fetch_links(self) -> list[str]:
        lokal_module.run()
        payload = json.loads(lokal_module.get_output_path().read_text(encoding="utf-8"))
        return [a.get("url") for a in payload.get("articles", []) if a.get("url")]

    def fetch_article(self, url: str) -> dict[str, Any] | None:
        # Lokal fetches via API bulk; individual fetch is not used.
        return None

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    def collect(self) -> list[dict[str, Any]]:
        lokal_module.run()
        path = lokal_module.get_output_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return list(payload.get("articles") or [])


def run() -> Path:
    lokal_module.run()
    return lokal_module.get_output_path()
