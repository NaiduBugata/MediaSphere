"""Incremental (per-cycle) email notifications.

After each 4-hour collection + AI categorization + MongoDB store, this module
emails ONLY the newly inserted articles that have not yet been emailed. Each
article is emailed exactly once, tracked by an `email_sent` flag on the
document.

Important: this cluster does not honour `$exists` / `$ne` query operators, so
all pending/emailed selection uses plain equality (`email_sent == False` /
`email_sent == True`). New articles are inserted with `email_sent = False`
(see mongo_store.upsert_articles), and existing documents can be initialised
with `backfill_flags`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import mongo_store

from . import config, data_service, email_service, html_template
from .logger import get_logger

logger = get_logger("reports.incremental")

PENDING_QUERY = {"email_sent": False}


def fetch_pending() -> list[dict]:
    """Return enriched articles awaiting an incremental email (email_sent == False)."""
    collection = mongo_store.get_collection()
    articles = [data_service.enrich(data_service._normalize(doc)) for doc in collection.find(PENDING_QUERY)]
    articles.sort(
        key=lambda a: a.get("created_dt") or datetime.min.replace(tzinfo=config.REPORT_TIMEZONE),
        reverse=True,
    )
    return articles


def backfill_flags(mark_as_sent: bool = True) -> int:
    """Initialise the email_sent flag on documents that predate this feature.

    Because `$exists` is unsupported on this cluster, we cannot target only the
    documents missing the field. Instead this sets the flag on documents that
    do not already carry an explicit True/False value by scanning once.

    Parameters:
        mark_as_sent: When True, legacy documents are marked as already emailed
            (recommended for production so the backlog is not re-sent). When
            False, they are marked pending (useful for a one-off catch-up).

    Returns:
        Number of documents updated.
    """
    collection = mongo_store.get_collection()
    updated = 0
    for doc in collection.find({}):
        if doc.get("email_sent") in (True, False):
            continue
        collection.update_one(
            {"post_id": doc.get("post_id")},
            {"$set": {"email_sent": bool(mark_as_sent)}},
        )
        updated += 1
    logger.info("Backfilled email_sent=%s on %d legacy document(s).", bool(mark_as_sent), updated)
    return updated


def _executive_summary(stats: dict[str, Any]) -> str:
    total = stats["total"]
    positive = stats["positive"]
    attention = stats["problems"]
    statements = stats["statement"] + stats["neutral"]

    def plural(n: int, singular: str, plural_word: str | None = None) -> str:
        return singular if n == 1 else (plural_word or singular + "s")

    article_word = plural(total, "article")
    parts = [
        f"{total} new {article_word} {plural(total, 'was', 'were')} collected during the latest monitoring cycle."
    ]
    segments = []
    if positive:
        segments.append(f"{positive} {plural(positive, 'is', 'are')} {plural(positive, 'a positive development', 'positive developments')}")
    if attention:
        segments.append(f"{attention} require{'s' if attention == 1 else ''} attention")
    if statements:
        segments.append(f"{statements} {plural(statements, 'is', 'are')} {plural(statements, 'a general statement', 'general statements')}")

    if segments:
        if len(segments) == 1:
            body = segments[0]
        else:
            body = ", ".join(segments[:-1]) + f", and {segments[-1]}"
        parts.append(f"Among them, {body}.")

    return " ".join(parts)


def _subject(now: datetime) -> str:
    local = now.astimezone(config.REPORT_TIMEZONE)
    return f"MediaSphere News Update | {local.strftime('%d %b %Y')} | {local.strftime('%I:%M %p')} IST"


def mark_emailed(post_ids: list[Any], batch_id: str, sent_at: str) -> int:
    """Mark the given articles as emailed (equality update per post_id)."""
    collection = mongo_store.get_collection()
    updated = 0
    for post_id in post_ids:
        result = collection.update_one(
            {"post_id": post_id},
            {"$set": {"email_sent": True, "email_sent_at": sent_at, "email_batch_id": batch_id}},
        )
        updated += result.modified_count
    return updated


def send_incremental_report(recipients: list[str] | None = None) -> dict[str, Any]:
    """Email the newly collected, not-yet-emailed articles (once each).

    Returns a result dict; never raises for expected failure conditions.
    """
    pending = fetch_pending()

    if not pending:
        logger.info("No new articles collected during this cycle.")
        return {"status": "skipped", "reason": "no_new_articles", "count": 0}

    if not config.EMAIL_ENABLED:
        logger.info("Incremental email disabled (EMAIL_ENABLED=false); skipping.")
        return {"status": "skipped", "reason": "email_disabled", "count": len(pending)}

    stats = data_service.compute_stats(pending)
    now = datetime.now(config.REPORT_TIMEZONE)
    batch_id = uuid.uuid4().hex
    summary = _executive_summary(stats)
    html = html_template.build_incremental_html(now, pending, stats, summary)
    subject = _subject(now)
    post_ids = [a.get("post_id") for a in pending]

    try:
        success, attempts, error = email_service.send_report(
            subject=subject,
            html_body=html,
            pdf_path=None,
            recipients=recipients,
        )
    except email_service.EmailConfigError as exc:
        logger.error("Incremental email not sent (configuration): %s", exc)
        return {"status": "error", "reason": "email_config", "error": str(exc), "count": len(pending)}

    if not success:
        # Do NOT mark as emailed; they remain pending and are retried next cycle.
        logger.error("Incremental email failed after %d attempt(s): %s", attempts, error)
        return {
            "status": "failed",
            "reason": "send_failed",
            "error": error,
            "attempts": attempts,
            "count": len(pending),
        }

    sent_at = datetime.now(timezone.utc).isoformat()
    marked = mark_emailed(post_ids, batch_id, sent_at)
    logger.info(
        "Incremental email sent | articles: %d | marked: %d | batch: %s",
        len(pending),
        marked,
        batch_id,
    )
    return {
        "status": "sent",
        "count": len(pending),
        "marked": marked,
        "batch_id": batch_id,
        "attempts": attempts,
        "subject": subject,
        "problems": stats["problems"],
        "positive": stats["positive"],
        "negative": stats["negative"],
        "recipients": recipients or config.REPORT_RECIPIENTS,
    }
