"""Run YouTube collector output through the Telugu news analyzer."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import ANALYZER_PATH, ANALYZER_TIMEOUT_SECONDS, LOG_BACKUP_COUNT, LOG_MAX_BYTES, LOG_PATH
from generate_article_txt import generate_article_txt_from_youtube_json
import mongo_store
from youtube import config as yt_config
from youtube import collector as yt_collector

logger = logging.getLogger("run_youtube_analysis")

NEWS_OUTPUT_FILE = yt_config.OUTPUT_DIR / "news_output.json"
PIPELINE_LOG_FILE = LOG_PATH / "youtube_analysis.log"


def configure_logging() -> None:
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
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
    for path in (
        yt_config.CHECKPOINT_FILE,
        yt_config.OUTPUT_DIR / "checkpoint.json",
        yt_config.OUTPUT_DIR / "failed_articles.json",
        yt_config.OUTPUT_DIR / "master_internal.json",
    ):
        if path.exists():
            path.unlink()
            logger.info("Removed stale file: %s", path)


def run_analyzer() -> subprocess.CompletedProcess[str]:
    yt_config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ANALYZER_PATH),
        "--input",
        str(yt_config.ARTICLE_PATH),
        "--output-dir",
        str(yt_config.OUTPUT_DIR),
    ]
    logger.info("Starting YouTube analyzer: %s", " ".join(command))
    env = os.environ.copy()
    env["CHECKPOINT_FILE"] = str(yt_config.CHECKPOINT_FILE)
    env["OUTPUT_DIR"] = str(yt_config.OUTPUT_DIR)
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
        "errors": [],
    }

    if not yt_config.YOUTUBE_ENABLED:
        logger.info("YouTube pipeline disabled (YOUTUBE_ENABLED=false); skipping.")
        return 0, empty

    if not yt_config.YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY is not set; skipping YouTube cycle.")
        empty["errors"].append("YOUTUBE_API_KEY missing")
        return 1, empty

    started_at = time.perf_counter()
    stats = dict(empty)

    try:
        logger.info("Collecting YouTube")
        collector_path = retry_call(yt_collector.run, label="youtube.collector")
        filtered_path, new_articles = mongo_store.filter_new_youtube_articles(
            collector_path,
            max_count=yt_config.YOUTUBE_MAX_NEW_PER_RUN,
        )
        stats["articles_fetched"] = len(new_articles)

        if not new_articles:
            logger.info("No new YouTube videos to analyze this cycle.")
            return 0, stats

        logger.info("Analyzing %d new YouTube article(s)", len(new_articles))
        generate_article_txt_from_youtube_json(
            filtered_path,
            yt_config.ARTICLE_PATH,
            min_chars=yt_config.YOUTUBE_MIN_CONTENT_CHARS,
        )
        clear_checkpoint()
        logger.info("Categorizing YouTube articles")
        result = run_analyzer()

        if result.stdout:
            logger.info("Analyzer stdout:\n%s", result.stdout.strip())
        if result.stderr:
            logger.warning("Analyzer stderr:\n%s", result.stderr.strip())
        if result.returncode != 0:
            logger.error("YouTube analyzer failed with exit code %s", result.returncode)
            stats["errors"].append(f"analyzer_exit_code={result.returncode}")
            return result.returncode, stats

        news_output = validate_news_output()
        stats["total"] = len(news_output)
        stored_ok = False
        try:
            logger.info("Saving MongoDB (YouTube)")
            upsert_stats = mongo_store.upsert_youtube_articles(news_output, filtered_path)
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
                "MongoDB upsert (YouTube) | inserted: %s | updated: %s | matched: %s | duplicates: %s",
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
            "YouTube cycle complete | articles: %s | inserted=%s | duplicates=%s | elapsed: %.2fs",
            len(news_output),
            stats["inserted"],
            stats["duplicates"],
            elapsed,
        )
        return (0 if stored_ok else 1), stats

    except subprocess.TimeoutExpired:
        logger.error("YouTube analyzer timed out after %s seconds", ANALYZER_TIMEOUT_SECONDS)
        stats["errors"].append("analyzer_timeout")
        return 1, stats
    except Exception as exc:
        logger.exception("YouTube pipeline cycle failed: %s", exc)
        stats["errors"].append(str(exc))
        return 1, stats


def run_forever() -> int:
    interval = yt_config.YOUTUBE_CHECK_INTERVAL
    logger.info("YouTube pipeline started | interval: %s seconds", interval)
    try:
        while True:
            exit_code, _stats = run_cycle()
            if exit_code != 0:
                logger.warning("YouTube cycle exit code %s; continuing", exit_code)
            next_run = datetime.now(timezone.utc) + timedelta(seconds=interval)
            logger.info("Next YouTube run at %s UTC", next_run.isoformat())
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("YouTube pipeline stopped by user")
        return 0

def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run the YouTube news analysis pipeline")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args(argv)

    if args.once:
        code, _stats = run_cycle()
        return code
    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
