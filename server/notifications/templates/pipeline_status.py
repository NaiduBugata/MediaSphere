"""Pipeline completion / status template."""

from __future__ import annotations

from typing import Any

from notifications.utils import safe_str


def build_text(stats: dict[str, Any]) -> str:
    return "\n".join(
        [
            "✅ PIPELINE COMPLETED",
            "",
            f"Articles Collected: {stats.get('articles_fetched', stats.get('fetched', 0))}",
            f"AI Processed: {stats.get('total', 0)}",
            f"Stored (inserted): {stats.get('inserted', 0)}",
            f"Duplicates: {stats.get('duplicates', 0)}",
            f"Lokal: {stats.get('lokal_processed', '—')}",
            f"YouTube: {stats.get('youtube_processed', '—')}",
            f"Sakshi: {stats.get('sakshi_processed', '—')}",
            f"Email Sent: {stats.get('email_sent', '—')}",
            f"WhatsApp Sent: {stats.get('whatsapp_sent', '—')}",
            f"Execution Time: {safe_str(stats.get('duration_seconds'), '—')}s",
            "",
            f"Status: {safe_str(stats.get('status'), 'Finished Successfully')}",
            "",
            "MediaSphere Intelligence Platform",
        ]
    )
