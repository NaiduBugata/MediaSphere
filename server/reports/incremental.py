"""Incremental email notifications — one email per newly collected article.

After each pipeline cycle (collect → categorize → store), sends a separate
email for every newly inserted article. Each article is emailed exactly once,
tracked via the `email_sent` flag on the MongoDB document.
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
    """Return enriched articles awaiting an email (email_sent == False)."""
    collection = mongo_store.get_collection()
    articles = [data_service.enrich(data_service._normalize(doc)) for doc in collection.find(PENDING_QUERY)]
    articles.sort(
        key=lambda a: a.get("created_dt") or datetime.min.replace(tzinfo=config.REPORT_TIMEZONE),
        reverse=True,
    )
    return articles


def fetch_by_post_ids(post_ids: list[Any]) -> list[dict]:
    """Return enriched, not-yet-emailed articles for the given post_ids."""
    if not post_ids:
        return []
    collection = mongo_store.get_collection()
    articles = []
    for post_id in post_ids:
        doc = collection.find_one({"post_id": post_id, "email_sent": False})
        if doc:
            articles.append(data_service.enrich(data_service._normalize(doc)))
    articles.sort(
        key=lambda a: a.get("created_dt") or datetime.min.replace(tzinfo=config.REPORT_TIMEZONE),
        reverse=True,
    )
    return articles


def backfill_flags(mark_as_sent: bool = True) -> int:
    """Initialise the email_sent flag on legacy documents."""
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


def _subject_for_article(article: dict, now: datetime) -> str:
    local = now.astimezone(config.REPORT_TIMEZONE)
    title = (article.get("title") or "News Update").strip()
    if len(title) > 55:
        title = title[:52] + "..."
    category = article.get("category") or "News"
    source = (article.get("source") or "lokal").capitalize()
    return f"MediaSphere Alert | {source} | {category} | {local.strftime('%d %b %Y %I:%M %p')} IST | {title}"


def mark_emailed(post_id: Any, batch_id: str, sent_at: str) -> bool:
    """Mark a single article as emailed. Returns True if the document was updated."""
    result = mongo_store.get_collection().update_one(
        {"post_id": post_id},
        {"$set": {"email_sent": True, "email_sent_at": sent_at, "email_batch_id": batch_id}},
    )
    return result.modified_count > 0


def send_incremental_report(
    recipients: list[str] | None = None,
    post_ids: list[Any] | None = None,
) -> dict[str, Any]:
    """Send one email per newly collected article.

    Parameters:
        recipients: Override recipient list.
        post_ids: When provided (pipeline cycle), email only these newly inserted
            articles. When omitted (CLI), email all pending (email_sent=false).

    Returns a result dict; never raises for expected failure conditions.
    """
    if post_ids is not None:
        articles = fetch_by_post_ids(post_ids)
        if not post_ids:
            logger.info("No new articles collected during this cycle.")
            return {"status": "skipped", "reason": "no_new_articles", "count": 0, "sent": 0, "failed": 0}
    else:
        articles = fetch_pending()

    if not articles:
        logger.info("No new articles to email during this cycle.")
        return {"status": "skipped", "reason": "no_new_articles", "count": 0, "sent": 0, "failed": 0}

    if not config.EMAIL_ENABLED:
        logger.info("Incremental email disabled (EMAIL_ENABLED=false); skipping.")
        return {"status": "skipped", "reason": "email_disabled", "count": len(articles), "sent": 0, "failed": 0}

    now = datetime.now(config.REPORT_TIMEZONE)
    batch_id = uuid.uuid4().hex
    sent_at = datetime.now(timezone.utc).isoformat()
    sent_count = 0
    failed_count = 0
    failed_ids: list[Any] = []
    subjects: list[str] = []

    for article in articles:
        post_id = article.get("post_id")
        subject = _subject_for_article(article, now)
        html = html_template.build_single_article_html(article, now)

        try:
            success, attempts, error = email_service.send_report(
                subject=subject,
                html_body=html,
                pdf_path=None,
                recipients=recipients,
            )
        except email_service.EmailConfigError as exc:
            logger.error("Incremental email not sent (configuration): %s", exc)
            return {
                "status": "error",
                "reason": "email_config",
                "error": str(exc),
                "count": len(articles),
                "sent": sent_count,
                "failed": len(articles) - sent_count,
            }

        if success:
            if mark_emailed(post_id, batch_id, sent_at):
                sent_count += 1
                subjects.append(subject)
                logger.info("Article email sent | post_id=%s | %s", post_id, subject[:80])
            else:
                logger.warning("Email sent but mark failed for post_id=%s", post_id)
                sent_count += 1
        else:
            failed_count += 1
            failed_ids.append(post_id)
            logger.error(
                "Article email failed | post_id=%s | attempts=%s | %s",
                post_id,
                attempts,
                error,
            )

    status = "sent" if sent_count and not failed_count else ("partial" if sent_count else "failed")
    logger.info(
        "Incremental emails complete | total: %d | sent: %d | failed: %d | batch: %s",
        len(articles),
        sent_count,
        failed_count,
        batch_id,
    )
    return {
        "status": status,
        "count": len(articles),
        "sent": sent_count,
        "failed": failed_count,
        "failed_post_ids": failed_ids,
        "batch_id": batch_id,
        "subjects": subjects,
        "recipients": recipients or config.REPORT_RECIPIENTS,
    }
