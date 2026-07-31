"""Failure / error alert template."""

from __future__ import annotations

from notifications.formatter import format_datetime
from notifications.utils import safe_str


def build_text(
    *,
    module: str,
    reason: str,
    retry_status: str = "N/A",
    server: str = "MediaSphere",
) -> str:
    return "\n".join(
        [
            "❌ PIPELINE FAILURE",
            "",
            f"Module: {safe_str(module, 'unknown')}",
            "Status: FAILED",
            f"Reason: {safe_str(reason, 'Unknown error')[:500]}",
            f"Time: {format_datetime(None)}",
            f"Retry Status: {safe_str(retry_status, 'N/A')}",
            f"Server: {safe_str(server, 'MediaSphere')}",
            "",
            "MediaSphere Intelligence Platform",
        ]
    )


def build_startup_text(*, environment: str, version: str, details: dict[str, str]) -> str:
    lines = [
        "🟢 MediaSphere Started",
        "",
        f"Environment: {environment}",
        f"Version: {version}",
    ]
    for key, value in details.items():
        lines.append(f"{key}: {value}")
    lines.extend(["", "MediaSphere Intelligence Platform"])
    return "\n".join(lines)


def build_shutdown_text(*, environment: str, version: str) -> str:
    return "\n".join(
        [
            "🔴 MediaSphere Shutting Down",
            "",
            f"Environment: {environment}",
            f"Version: {version}",
            f"Time: {format_datetime(None)}",
            "",
            "Graceful shutdown initiated.",
            "",
            "MediaSphere Intelligence Platform",
        ]
    )


def build_health_text(checks: dict[str, str]) -> str:
    lines = ["🩺 MediaSphere Health Report", "", f"Time: {format_datetime(None)}", ""]
    all_ok = all(str(v).lower() in ("ok", "healthy", "connected", "running", "ready", "true") for v in checks.values())
    for name, status in checks.items():
        lines.append(f"{name}: {status}")
    lines.extend(
        [
            "",
            "Everything Healthy" if all_ok else "Attention required — see statuses above.",
            "",
            "MediaSphere Intelligence Platform",
        ]
    )
    return "\n".join(lines)
