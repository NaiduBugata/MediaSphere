"""Report service facade — delegates to reports package."""

from __future__ import annotations

from datetime import date
from typing import Any


def build_report(target: date | None = None) -> dict[str, Any]:
    """Build a constituency intelligence report for the target date."""
    from reports import report_generator

    return report_generator.build_report(target or date.today())


def generate_and_send(target: date | None = None, *, force: bool = False) -> dict[str, Any]:
    """Generate and send a report."""
    from reports import report_generator

    return report_generator.generate_and_send(target, force=force)
