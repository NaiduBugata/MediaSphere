"""Orchestrates the full daily report pipeline.

Steps: fetch data -> compute stats -> AI summary -> HTML + PDF -> email ->
persist history. Handles de-duplication so the same day is never emailed
twice, and never raises in a way that crashes the scheduler.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from . import ai_summary, config, data_service, db_service, email_service, html_template, pdf_generator
from .logger import get_logger

logger = get_logger("reports.generator")


def _subject(target: date) -> str:
    return f"MediaSphere Daily Constituency Report - {target.strftime('%d %B %Y')}"


def build_report(target: date) -> dict[str, Any]:
    """Build (but do not send) the report artifacts for a target date."""
    generated_at = datetime.now(config.REPORT_TIMEZONE)
    articles = data_service.fetch_articles_for_day(target)
    stats = data_service.compute_stats(articles)
    summary = ai_summary.generate_executive_summary(target, articles, stats)
    html = html_template.build_email_html(target, generated_at, articles, stats, summary)
    pdf_path = pdf_generator.generate_pdf(target, generated_at, articles, stats, summary)
    return {
        "target": target,
        "generated_at": generated_at,
        "articles": articles,
        "stats": stats,
        "summary": summary,
        "html": html,
        "pdf_path": pdf_path,
        "subject": _subject(target),
    }


def generate_and_send(
    target: date | None = None,
    *,
    force: bool = False,
    recipients: list[str] | None = None,
) -> dict[str, Any]:
    """Generate and email the report for `target` (defaults to yesterday IST).

    De-duplicates on report_date unless `force` is True. Returns a result dict
    describing the outcome; never raises for expected failure conditions.
    """
    target = target or data_service.previous_day()

    if not force and db_service.already_sent(target):
        logger.info("Report for %s already sent; skipping (dedup).", target.isoformat())
        return {"status": "skipped", "reason": "already_sent", "report_date": target.isoformat()}

    try:
        report = build_report(target)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Report build failed for %s: %s", target, exc)
        db_service.record_failed(target, 0, f"build_failed: {exc}")
        return {"status": "error", "reason": "build_failed", "error": str(exc), "report_date": target.isoformat()}

    to = recipients or config.REPORT_RECIPIENTS
    db_service.record_generation(target, report["stats"], to, str(report["pdf_path"]))

    try:
        success, attempts, error = email_service.send_report(
            subject=report["subject"],
            html_body=report["html"],
            pdf_path=report["pdf_path"],
            recipients=to,
        )
    except email_service.EmailConfigError as exc:
        logger.error("Email not sent (configuration): %s", exc)
        db_service.record_failed(target, 0, f"config_error: {exc}")
        return {
            "status": "error",
            "reason": "email_config",
            "error": str(exc),
            "report_date": target.isoformat(),
            "pdf_path": str(report["pdf_path"]),
        }

    if success:
        db_service.record_sent(target, attempts)
        logger.info("Daily report for %s generated and sent.", target.isoformat())
        status = "sent"
    else:
        db_service.record_failed(target, attempts, error or "unknown")
        status = "failed"

    return {
        "status": status,
        "report_date": target.isoformat(),
        "recipients": to,
        "attempts": attempts,
        "error": None if success else error,
        "articles_included": report["stats"]["total"],
        "problems_count": report["stats"]["problems"],
        "positive_count": report["stats"]["positive"],
        "negative_count": report["stats"]["negative"],
        "pdf_path": str(report["pdf_path"]),
        "subject": report["subject"],
    }
