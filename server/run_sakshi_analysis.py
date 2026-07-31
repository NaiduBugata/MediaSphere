"""Run Sakshi collector output through the Telugu news analyzer."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import ANALYZER_PATH, ANALYZER_TIMEOUT_SECONDS, LOG_BACKUP_COUNT, LOG_MAX_BYTES, LOG_PATH
from collectors import config as sakshi_config
from collectors import sakshi_collector
from generate_article_txt import generate_article_txt_from_json
import mongo_store

logger = logging.getLogger("run_sakshi_analysis")

NEWS_OUTPUT_FILE = sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR / "news_output.json"
PIPELINE_LOG_FILE = LOG_PATH / "sakshi_analysis.log"


def configure_logging() -> None:
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        PIPELINE_LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)


def clear_checkpoint() -> None:
    sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (
        sakshi_config.SAKSHI_CHECKPOINT_FILE,
        sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR / "checkpoint.json",
        sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR / "failed_articles.json",
        sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR / "master_internal.json",
    ):
        if path.exists():
            path.unlink()
            logger.info("Removed stale file: %s", path)


def run_analyzer() -> subprocess.CompletedProcess[str]:
    sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ANALYZER_PATH),
        "--input",
        str(sakshi_config.SAKSHI_ARTICLE_PATH),
        "--output-dir",
        str(sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR),
    ]
    logger.info("Starting Sakshi analyzer: %s", " ".join(command))
    env = os.environ.copy()
    env["CHECKPOINT_FILE"] = str(sakshi_config.SAKSHI_CHECKPOINT_FILE)
    env["OUTPUT_DIR"] = str(sakshi_config.SAKSHI_ANALYZER_OUTPUT_DIR)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=ANALYZER_TIMEOUT_SECONDS,
        env=env,
    )


def validate_news_output() -> list:
    if not NEWS_OUTPUT_FILE.exists():
        raise FileNotFoundError(f"Analyzer output not found: {NEWS_OUTPUT_FILE}")
    payload = json.loads(NEWS_OUTPUT_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("news_output.json must contain a JSON array")
    return payload


def send_incremental_email() -> None:
    from reports import config as report_config

    if not report_config.EMAIL_ENABLED:
        logger.info("Incremental email disabled; skipping.")
        return
    try:
        from reports import incremental

        result = incremental.send_incremental_report()
        status = result.get("status")
        if status in ("sent", "partial"):
            logger.info(
                "Incremental emails | sent: %s | failed: %s",
                result.get("sent"),
                result.get("failed"),
            )
        elif status == "skipped":
            logger.info("Incremental email skipped (%s).", result.get("reason"))
    except Exception as exc:
        logger.error("Incremental email failed (cycle continues): %s", exc)


def run_cycle() -> tuple[int, dict]:
    from retry_utils import retry_call

    empty = {
        "inserted": 0,
        "updated": 0,
        "matched": 0,
        "duplicates": 0,
        "total": 0,
        "articles_fetched": 0,
        "fetched": 0,
        "accepted": 0,
        "rejected": 0,
        "rejected_reasons": {},
        "errors": [],
    }

    if not sakshi_config.SAKSHI_ENABLED:
        logger.info("Sakshi pipeline disabled (SAKSHI_ENABLED=false); skipping.")
        return 0, empty

    started_at = time.perf_counter()
    stats = dict(empty)

    try:
        logger.info("Collecting Sakshi (constituency-filtered)")
        collector_path = retry_call(sakshi_collector.run, label="sakshi.collector")
        payload = json.loads(Path(collector_path).read_text(encoding="utf-8"))
        articles = payload.get("articles") or []
        filter_stats = payload.get("filter_stats") or {}
        stats["articles_fetched"] = len(articles)
        stats["fetched"] = int(filter_stats.get("fetched") or len(articles))
        stats["accepted"] = int(filter_stats.get("accepted") or len(articles))
        stats["rejected"] = int(filter_stats.get("rejected") or 0)
        stats["rejected_reasons"] = dict(filter_stats.get("rejected_reasons") or {})

        logger.info(
            "Sakshi filter | fetched=%s | accepted=%s | rejected=%s | reasons=%s",
            stats["fetched"],
            stats["accepted"],
            stats["rejected"],
            stats["rejected_reasons"],
        )

        if not articles:
            logger.info("No constituency-valid Sakshi articles to analyze this cycle.")
            return 0, stats

        article_path = generate_article_txt_from_json(
            collector_path,
            sakshi_config.SAKSHI_ARTICLE_PATH,
        )
        logger.info("Generated analyzer input: %s", article_path)

        clear_checkpoint()
        logger.info("Categorizing Sakshi articles")
        result = run_analyzer()

        if result.stdout:
            logger.info("Analyzer stdout:\n%s", result.stdout.strip())
        if result.stderr:
            logger.warning("Analyzer stderr:\n%s", result.stderr.strip())
        if result.returncode != 0:
            logger.error("Sakshi analyzer failed with exit code %s", result.returncode)
            stats["errors"].append(f"analyzer_exit_code={result.returncode}")
            return result.returncode, stats

        news_output = validate_news_output()
        stats["total"] = len(news_output)
        stored_ok = False
        try:
            logger.info("Saving MongoDB (Sakshi)")
            upsert_stats = mongo_store.upsert_sakshi_articles(news_output, collector_path)
            stored_ok = True
            stats.update(
                {
                    "inserted": upsert_stats.get("inserted", 0),
                    "updated": upsert_stats.get("updated", 0),
                    "matched": upsert_stats.get("matched", 0),
                    "duplicates": upsert_stats.get("duplicates", 0),
                    "total": upsert_stats.get("total", len(news_output)),
                }
            )
            logger.info(
                "MongoDB upsert (Sakshi) | inserted: %s | updated: %s | matched: %s | duplicates: %s",
                stats["inserted"],
                stats["updated"],
                stats["matched"],
                stats["duplicates"],
            )
        except Exception as exc:
            logger.error("MongoDB store failed: %s", exc)
            stats["errors"].append(f"mongodb:{exc}")

        if stored_ok:
            send_incremental_email()

        elapsed = time.perf_counter() - started_at
        logger.info(
            "Sakshi cycle complete | fetched=%s | accepted=%s | rejected=%s | "
            "inserted=%s | duplicates=%s | elapsed: %.2fs",
            stats["fetched"],
            stats["accepted"],
            stats["rejected"],
            stats["inserted"],
            stats["duplicates"],
            elapsed,
        )
        return (0 if stored_ok else 1), stats

    except subprocess.TimeoutExpired:
        logger.error("Analyzer timed out after %s seconds", ANALYZER_TIMEOUT_SECONDS)
        stats["errors"].append("analyzer_timeout")
        return 1, stats
    except Exception as exc:
        logger.exception("Sakshi pipeline cycle failed: %s", exc)
        stats["errors"].append(str(exc))
        return 1, stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Sakshi news analysis pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single pipeline cycle and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    logger.info("Sakshi analysis pipeline started (one-shot mode)")
    code, _stats = run_cycle()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
