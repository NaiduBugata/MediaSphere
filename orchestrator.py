import csv
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    ANALYZER_PATH,
    ANALYZER_TIMEOUT_SECONDS,
    ARTICLE_PATH,
    ARTICLE_RETRY_COUNT,
    ARTICLE_SEPARATOR,
    CHECK_INTERVAL_SECONDS,
    CSV_PATH,
    CSV_RETRY_COUNT,
    FETCH_RETRY_COUNT,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    LOG_PATH,
    OUTPUT_JSON_FILES,
    OUTPUT_PATH,
    PIPELINE_LOG_PATH,
    PIPELINE_STATUS_PATH,
    RETRY_BACKOFF_SECONDS,
)
from generate_article_txt import generate_article_txt
from lokal_news_collector import LokalNewsCollector

logger = logging.getLogger("pipeline_orchestrator")


class StageResult:
    def __init__(self, status: str, message: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        self.status = status
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "message": self.message, **self.details}


class PipelineOrchestrator:
    def __init__(self) -> None:
        self.logger = logger
        self.cycle_id = 0

    def configure_logging(self) -> None:
        LOG_PATH.mkdir(parents=True, exist_ok=True)
        for handler in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(handler)
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        file_handler = RotatingFileHandler(PIPELINE_LOG_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)

    def health_check(self) -> StageResult:
        issues: List[str] = []
        if not OUTPUT_PATH.exists():
            OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        if not OUTPUT_PATH.is_dir():
            issues.append("output path is not a directory")
        if not CSV_PATH.exists():
            CSV_PATH.touch(exist_ok=True)
        if not ARTICLE_PATH.parent.exists():
            ARTICLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not ANALYZER_PATH.exists():
            issues.append("analyzer file missing")
        if not os.access(ARTICLE_PATH.parent, os.W_OK):
            issues.append("article directory not writable")
        if not os.access(OUTPUT_PATH, os.W_OK):
            issues.append("output directory not writable")
        if not shutil.which(sys.executable):
            issues.append("python executable unavailable")
        if issues:
            return StageResult("FAILED", "Health check failed", {"issues": issues})
        return StageResult("SUCCESS", "Health check passed")

    def run_stage(self, stage_name: str, func, *args, **kwargs) -> StageResult:
        try:
            self.logger.info("Stage Started | %s", stage_name)
            result = func(*args, **kwargs)
            self.logger.info("Stage Finished | %s | %s", stage_name, result.status)
            return result
        except Exception as exc:
            self.logger.exception("Stage Failed | %s | %s", stage_name, exc)
            return StageResult("FAILED", str(exc))

    def stage_fetch_news(self) -> StageResult:
        started_at = datetime.now(timezone.utc)
        try:
            collector = LokalNewsCollector(CSV_PATH)
            for attempt in range(1, FETCH_RETRY_COUNT + 1):
                csv_path = collector.run()
                if csv_path.exists():
                    return StageResult("SUCCESS", "Fetch completed", {"execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3), "retry_count": attempt - 1, "csv_path": str(csv_path)})
                if attempt < FETCH_RETRY_COUNT:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            return StageResult("FAILED", "Fetch produced no csv output")
        except Exception as exc:
            return StageResult("FAILED", str(exc), {"execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})

    def stage_update_csv(self) -> StageResult:
        started_at = datetime.now(timezone.utc)
        try:
            if not CSV_PATH.exists():
                return StageResult("FAILED", "CSV missing")
            with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            if not rows:
                return StageResult("WARNING", "CSV contains no rows")
            seen_ids = set()
            seen_titles = set()
            seen_content = set()
            duplicates = []
            for row in rows:
                row_id = (row.get("id") or "").strip()
                title = (row.get("title") or "").strip()
                content = (row.get("content") or "").strip()
                if row_id and row_id in seen_ids:
                    duplicates.append(f"duplicate_id:{row_id}")
                if title and title in seen_titles:
                    duplicates.append(f"duplicate_title:{title}")
                if content and content in seen_content:
                    duplicates.append(f"duplicate_content:{content}")
                seen_ids.add(row_id)
                seen_titles.add(title)
                seen_content.add(content)
            if duplicates:
                return StageResult("WARNING", "CSV duplicates detected", {"duplicates": duplicates, "execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})
            return StageResult("SUCCESS", "CSV validated", {"rows": len(rows), "execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})
        except Exception as exc:
            return StageResult("FAILED", str(exc))

    def stage_generate_article(self) -> StageResult:
        started_at = datetime.now(timezone.utc)
        if not CSV_PATH.exists():
            return StageResult("SKIPPED", "CSV missing")
        try:
            with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except Exception as exc:
            return StageResult("FAILED", str(exc))
        if not rows:
            return StageResult("SKIPPED", "CSV contains no rows")
        for attempt in range(1, ARTICLE_RETRY_COUNT + 1):
            try:
                article_path = generate_article_txt(csv_path=CSV_PATH, article_path=ARTICLE_PATH)
                content = article_path.read_text(encoding="utf-8").strip() if article_path.exists() else ""
                if not content:
                    return StageResult("SKIPPED", "article.txt is empty", {"execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})
                if ARTICLE_SEPARATOR not in content:
                    raise ValueError("article.txt separator format invalid")
                return StageResult("SUCCESS", "article.txt generated", {"article_path": str(article_path), "execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})
            except Exception as exc:
                if attempt >= ARTICLE_RETRY_COUNT:
                    return StageResult("FAILED", str(exc), {"execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        return StageResult("FAILED", "article generation failed")

    def stage_validate_article(self) -> StageResult:
        if not ARTICLE_PATH.exists():
            return StageResult("SKIPPED", "article.txt missing")
        try:
            content = ARTICLE_PATH.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return StageResult("FAILED", "article.txt is not valid UTF-8")
        if not content.strip():
            return StageResult("SKIPPED", "article.txt is empty")
        blocks = [block for block in content.split(ARTICLE_SEPARATOR) if block.strip()]
        if not blocks:
            return StageResult("SKIPPED", "no article blocks found")
        return StageResult("SUCCESS", "article.txt validated", {"article_blocks": len(blocks)})

    def stage_execute_analyzer(self) -> StageResult:
        started_at = datetime.now(timezone.utc)
        try:
            process = subprocess.run(
                [sys.executable, str(ANALYZER_PATH), "--input", str(ARTICLE_PATH), "--output-dir", str(OUTPUT_PATH)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=ANALYZER_TIMEOUT_SECONDS,
            )
            return StageResult(
                "SUCCESS" if process.returncode == 0 else "FAILED",
                "Analyzer completed",
                {
                    "exit_code": process.returncode,
                    "execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3),
                    "stdout_length": len(process.stdout or ""),
                    "stderr_length": len(process.stderr or ""),
                },
            )
        except subprocess.TimeoutExpired as exc:
            return StageResult("FAILED", "Analyzer timed out", {"execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3), "timeout_seconds": 300})
        except Exception as exc:
            return StageResult("FAILED", str(exc), {"execution_time_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3)})

    def stage_verify_outputs(self) -> StageResult:
        if not ARTICLE_PATH.exists() or not ARTICLE_PATH.read_text(encoding="utf-8").strip():
            return StageResult("SKIPPED", "Analyzer not run because article input was empty")
        missing = []
        for filename in OUTPUT_JSON_FILES:
            path = OUTPUT_PATH / filename
            if not path.exists():
                missing.append(filename)
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    json.load(handle)
            except Exception as exc:
                missing.append(f"{filename}:{exc}")
        if missing:
            return StageResult("FAILED", "Output verification failed", {"missing_or_invalid": missing})
        return StageResult("SUCCESS", "Outputs verified")

    def write_status_report(self, report: Dict[str, Any]) -> None:
        PIPELINE_STATUS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def run_cycle(self) -> Dict[str, Any]:
        self.cycle_id += 1
        started_at = datetime.now(timezone.utc)
        self.logger.info("Cycle Started | cycle_id=%s", self.cycle_id)
        results: Dict[str, Any] = {
            "cycle_id": self.cycle_id,
            "start_time": started_at.isoformat(),
            "fetch": "SKIPPED",
            "csv": "SKIPPED",
            "article_generation": "SKIPPED",
            "article_validation": "SKIPPED",
            "analyzer": "SKIPPED",
            "output_validation": "SKIPPED",
            "articles_fetched": 0,
            "articles_processed": 0,
            "articles_failed": 0,
            "next_run": "",
        }

        health = self.health_check()
        if health.status != "SUCCESS":
            self.logger.warning("Health check failed: %s", health.message)
            results["article_validation"] = "WARNING"
            results["analyzer"] = "WARNING"
            results["output_validation"] = "WARNING"
        else:
            fetch_result = self.run_stage("fetch_news", self.stage_fetch_news)
            results["fetch"] = fetch_result.status
            if fetch_result.status == "SUCCESS":
                results["articles_fetched"] = int(fetch_result.details.get("retry_count", 0)) + 1

            csv_result = self.run_stage("csv_update", self.stage_update_csv)
            results["csv"] = csv_result.status

            article_result = self.run_stage("article_generation", self.stage_generate_article)
            results["article_generation"] = article_result.status

            validation_result = self.run_stage("article_validation", self.stage_validate_article)
            results["article_validation"] = validation_result.status

            if validation_result.status == "SUCCESS":
                analyzer_result = self.run_stage("analyzer_execution", self.stage_execute_analyzer)
                results["analyzer"] = analyzer_result.status
            else:
                results["analyzer"] = "SKIPPED"

            output_result = self.run_stage("output_validation", self.stage_verify_outputs)
            results["output_validation"] = output_result.status

        ended_at = datetime.now(timezone.utc)
        duration = round((ended_at - started_at).total_seconds(), 3)
        results["end_time"] = ended_at.isoformat()
        results["duration_seconds"] = duration
        results["next_run"] = (ended_at + __import__("datetime").timedelta(seconds=CHECK_INTERVAL_SECONDS)).isoformat()
        self.write_status_report(results)
        self.logger.info("Cycle Finished | cycle_id=%s | duration=%.3fs", self.cycle_id, duration)
        return results

    def run_forever(self) -> None:
        self.configure_logging()
        while True:
            try:
                self.run_cycle()
            except Exception as exc:
                self.logger.exception("Pipeline error: %s", exc)
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    orchestrator = PipelineOrchestrator()
    orchestrator.run_forever()
