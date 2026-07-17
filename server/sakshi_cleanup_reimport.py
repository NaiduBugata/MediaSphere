"""One-shot: delete all Sakshi Mongo articles, then run a fresh filtered collection."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("sakshi_cleanup_reimport")


def main() -> int:
    import mongo_store
    from run_sakshi_analysis import configure_logging, run_cycle

    configure_logging()

    before_sakshi = mongo_store.count_by_source("sakshi")
    before_lokal = mongo_store.count_by_source("lokal")
    before_youtube = mongo_store.count_by_source("youtube")
    logger.info(
        "Before cleanup | sakshi=%s | lokal=%s | youtube=%s",
        before_sakshi,
        before_lokal,
        before_youtube,
    )

    deleted = mongo_store.delete_sakshi_articles()
    logger.info("Deleted %s Sakshi articles.", deleted)

    after_delete = mongo_store.count_by_source("sakshi")
    lokal_ok = mongo_store.count_by_source("lokal") == before_lokal
    youtube_ok = mongo_store.count_by_source("youtube") == before_youtube
    logger.info(
        "After delete | sakshi=%s | lokal_unchanged=%s | youtube_unchanged=%s",
        after_delete,
        lokal_ok,
        youtube_ok,
    )
    if after_delete != 0:
        logger.error("Sakshi delete incomplete; aborting fresh import.")
        return 1
    if not lokal_ok or not youtube_ok:
        logger.error("Lokal/YouTube counts changed during Sakshi delete; aborting.")
        return 1

    code, stats = run_cycle()
    after_sakshi = mongo_store.count_by_source("sakshi")

    summary = {
        "deleted_old_sakshi": deleted,
        "fetched": stats.get("fetched"),
        "accepted": stats.get("accepted"),
        "rejected": stats.get("rejected"),
        "rejected_reasons": stats.get("rejected_reasons"),
        "inserted": stats.get("inserted"),
        "duplicates": stats.get("duplicates"),
        "sakshi_count_after": after_sakshi,
        "lokal_count": mongo_store.count_by_source("lokal"),
        "youtube_count": mongo_store.count_by_source("youtube"),
        "exit_code": code,
    }
    report_path = SERVER_DIR / "output" / "sakshi" / "cleanup_reimport_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Cleanup + reimport summary: %s", summary)
    logger.info("Report written to %s", report_path)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
