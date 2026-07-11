"""Run the Lokal JSON collector output through the Telugu news analyzer."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import (
    ANALYZER_PATH,
    ANALYZER_TIMEOUT_SECONDS,
    ARTICLE_PATH,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    LOG_PATH,
    OUTPUT_PATH,
)
from generate_article_txt import generate_article_txt_from_json
import lokal_collector
import mongo_store

logger = logging.getLogger("run_lokal_analysis")

CHECKPOINT_FILE = Path("checkpoint.json")
NEWS_OUTPUT_FILE = OUTPUT_PATH / "news_output.json"
FAILED_ARTICLES_FILE = OUTPUT_PATH / "failed_articles.json"
PIPELINE_LOG_FILE = LOG_PATH / "lokal_analysis.log"


def configure_logging() -> None:
    """
    Configure console and rotating file logging for the pipeline.

    Purpose:
        Provide consistent log output for scheduled and one-shot runs.

    Parameters:
        None.

    Returns:
        None.
    """
    LOG_PATH.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # Windows consoles default to cp1252, which crashes the log handler on
    # Telugu text. Force UTF-8 so the unattended worker logs cleanly.
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


def refresh_collector() -> Path:
    """
    Refresh the Lokal collector JSON for the current 7-day window.

    Purpose:
        Pull the latest posts, including any newly published articles.

    Parameters:
        None.

    Returns:
        Path to the refreshed collector JSON file.
    """
    json_path = lokal_collector.get_output_path()
    logger.info("Refreshing collector JSON: %s", json_path)
    lokal_collector.run()

    if not json_path.exists():
        raise FileNotFoundError(f"Collector did not produce expected JSON: {json_path}")

    return json_path


def clear_checkpoint() -> None:
    """
    Remove the analyzer checkpoint so all current articles are processed.

    Purpose:
        Avoid skipping articles from a stale checkpoint during a fresh run.

    Parameters:
        None.

    Returns:
        None.
    """
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        logger.info("Removed stale checkpoint: %s", CHECKPOINT_FILE)

    if FAILED_ARTICLES_FILE.exists():
        FAILED_ARTICLES_FILE.unlink()
        logger.info("Removed stale failed-articles file: %s", FAILED_ARTICLES_FILE)


def run_analyzer() -> subprocess.CompletedProcess[str]:
    """
    Invoke the Telugu news analyzer as a subprocess.

    Purpose:
        Run the existing analyzer unchanged with article.txt as input.

    Parameters:
        None.

    Returns:
        CompletedProcess result from the analyzer subprocess.
    """
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(ANALYZER_PATH),
        "--input",
        str(ARTICLE_PATH),
        "--output-dir",
        str(OUTPUT_PATH),
    ]
    logger.info("Starting analyzer: %s", " ".join(command))

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=ANALYZER_TIMEOUT_SECONDS,
    )


def validate_news_output() -> list:
    """
    Load and validate the analyzer's public JSON output.

    Purpose:
        Confirm the pipeline produced readable analyzed news JSON.

    Parameters:
        None.

    Returns:
        Parsed news_output.json payload.

    Raises:
        FileNotFoundError: When news_output.json is missing.
        ValueError: When news_output.json is not valid JSON or not a list.
    """
    if not NEWS_OUTPUT_FILE.exists():
        raise FileNotFoundError(f"Analyzer output not found: {NEWS_OUTPUT_FILE}")

    payload = json.loads(NEWS_OUTPUT_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("news_output.json must contain a JSON array")

    return payload


def send_incremental_email() -> None:
    """Email each pending article individually after a successful store.

    Sends one email per article with email_sent=false (new inserts and retries
    from prior failed sends). Successfully emailed articles are marked email_sent=true.
    """
    from reports import config as report_config

    if not report_config.EMAIL_ENABLED:
        logger.info("Incremental email disabled (EMAIL_ENABLED=false); skipping.")
        return

    try:
        from reports import incremental

        result = incremental.send_incremental_report()
        status = result.get("status")
        if status in ("sent", "partial"):
            logger.info(
                "Incremental emails | sent: %s | failed: %s | batch: %s",
                result.get("sent"),
                result.get("failed"),
                result.get("batch_id"),
            )
        elif status == "skipped":
            logger.info("Incremental email skipped (%s).", result.get("reason"))
        else:
            logger.warning("Incremental email issues | %s", result)
    except Exception as exc:
        logger.error("Incremental email step failed (cycle continues): %s", exc)


def run_cycle() -> int:
    """
    Execute one full Lokal JSON to analyzer pipeline cycle.

    Purpose:
        Chain collector refresh -> article.txt -> analyzer -> news_output.json.

    Parameters:
        None.

    Returns:
        Process exit code (0 on success, non-zero on failure).
    """
    started_at = time.perf_counter()

    try:
        json_path = refresh_collector()
        article_path = generate_article_txt_from_json(json_path, ARTICLE_PATH)
        logger.info("Generated analyzer input: %s", article_path)

        clear_checkpoint()
        result = run_analyzer()

        if result.stdout:
            logger.info("Analyzer stdout:\n%s", result.stdout.strip())
        if result.stderr:
            logger.warning("Analyzer stderr:\n%s", result.stderr.strip())

        if result.returncode != 0:
            logger.error("Analyzer failed with exit code %s", result.returncode)
            return result.returncode

        news_output = validate_news_output()

        stored_ok = False
        try:
            stats = mongo_store.upsert_articles(news_output, json_path)
            stored_ok = True
            logger.info(
                "MongoDB upsert | inserted: %s | updated: %s | matched: %s | total: %s",
                stats["inserted"],
                stats["updated"],
                stats["matched"],
                stats["total"],
            )
        except Exception as exc:
            logger.error("MongoDB store failed (JSON output still written): %s", exc)

        if stored_ok:
            send_incremental_email()

        elapsed = time.perf_counter() - started_at
        logger.info(
            "Cycle complete | articles: %s | output: %s | elapsed: %.2fs",
            len(news_output),
            NEWS_OUTPUT_FILE,
            elapsed,
        )
        return 0

    except subprocess.TimeoutExpired:
        logger.error("Analyzer timed out after %s seconds", ANALYZER_TIMEOUT_SECONDS)
        return 1
    except Exception as exc:
        logger.exception("Pipeline cycle failed: %s", exc)
        return 1


def run_forever() -> int:
    """
    Run the pipeline continuously on the configured interval.

    Purpose:
        Keep the 7-day news feed updated as new posts are published.

    Parameters:
        None.

    Returns:
        Process exit code (0 on clean shutdown, non-zero on unexpected failure).
    """
    interval = lokal_collector.CHECK_INTERVAL
    logger.info(
        "Production pipeline started | interval: %s seconds (%s hours)",
        interval,
        interval / 3600,
    )

    try:
        while True:
            exit_code = run_cycle()
            if exit_code != 0:
                logger.warning("Cycle finished with exit code %s; continuing scheduler", exit_code)

            next_run = datetime.now(timezone.utc) + timedelta(seconds=interval)
            logger.info("Next run scheduled at %s UTC", next_run.isoformat())
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Pipeline stopped by user")
        return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments for the pipeline runner.

    Purpose:
        Support one-shot and continuous production modes.

    Parameters:
        argv: Optional argument list override.

    Returns:
        Parsed argparse namespace.
    """
    parser = argparse.ArgumentParser(description="Run the Lokal news analysis pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single pipeline cycle and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for the Lokal analysis runner.

    Purpose:
        Configure logging and execute one or continuous pipeline runs.

    Parameters:
        argv: Optional argument list override.

    Returns:
        Process exit code.
    """
    configure_logging()
    args = parse_args(argv)

    if args.once:
        logger.info("Lokal analysis pipeline started (one-shot mode)")
        return run_cycle()

    return run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
