"""WSGI entry point for production servers (gunicorn / waitress / uWSGI).

Exposes the Flask ``app``. By default the API web service does NOT start the
report scheduler or send emails — those belong on a separate worker process.

Run with, e.g.:
    gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 wsgi:app
"""

from __future__ import annotations

import os

import mongo_store
from api.app import app

# Warm up MongoDB before accepting requests (avoids SRV/dns import races).
try:
    mongo_store.warmup()
except Exception:
    pass


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


if _flag("REPORT_SCHEDULER_ON_API"):
    from reports import scheduler

    scheduler.start(run_catch_up=_flag("REPORT_CATCHUP_ON_START"))

if _flag("PIPELINE_ON_API"):
    import pipeline_scheduler

    pipeline_scheduler.start(run_catch_up=_flag("PIPELINE_CATCHUP_ON_START", "true"))

if __name__ == "__main__":
    app.run()
