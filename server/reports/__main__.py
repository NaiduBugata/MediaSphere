"""CLI for the daily report.

Examples:
    python -m reports send-now                 # send yesterday's report (dedup applies)
    python -m reports send-now --force         # regenerate & resend even if already sent
    python -m reports send-now --date 2026-07-03
    python -m reports build --date 2026-07-03  # build artifacts only (no email)
    python -m reports history
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime

from . import config, db_service, incremental, report_generator
from .logger import get_logger

logger = get_logger("reports.cli")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(description="MediaSphere daily report CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    send = sub.add_parser("send-now", help="Generate and email a report")
    send.add_argument("--date", help="Target report date (YYYY-MM-DD); defaults to yesterday IST")
    send.add_argument("--force", action="store_true", help="Ignore dedup and resend")

    build = sub.add_parser("build", help="Build report artifacts without emailing")
    build.add_argument("--date", help="Target report date (YYYY-MM-DD); defaults to yesterday IST")

    sub.add_parser("history", help="Show report history")

    sub.add_parser("send-incremental", help="Email newly collected (not-yet-emailed) articles")

    backfill = sub.add_parser("backfill-flags", help="Initialise email_sent on legacy documents")
    backfill.add_argument(
        "--pending",
        action="store_true",
        help="Mark legacy docs as pending (email_sent=false) instead of already sent",
    )

    args = parser.parse_args()

    if args.command == "send-now":
        result = report_generator.generate_and_send(_parse_date(args.date), force=args.force)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") in ("sent", "skipped") else 1

    if args.command == "build":
        target = _parse_date(args.date) or report_generator.data_service.previous_day()
        report = report_generator.build_report(target)
        print(json.dumps(
            {
                "report_date": target.isoformat(),
                "articles_included": report["stats"]["total"],
                "problems": report["stats"]["problems"],
                "positive": report["stats"]["positive"],
                "pdf_path": str(report["pdf_path"]),
            },
            indent=2,
        ))
        return 0

    if args.command == "history":
        print(json.dumps(db_service.history(), indent=2, default=str))
        return 0

    if args.command == "send-incremental":
        result = incremental.send_incremental_report()
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") in ("sent", "skipped") else 1

    if args.command == "backfill-flags":
        count = incremental.backfill_flags(mark_as_sent=not args.pending)
        print(json.dumps({"updated": count, "marked_as_sent": not args.pending}, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
