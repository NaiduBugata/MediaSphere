"""WSGI entry point for production servers (gunicorn / waitress / uWSGI).

Exposes the Flask ``app``. By default the API web service does NOT start the
report scheduler or send emails — those belong on a separate worker process.

Run with, e.g.:
    gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 wsgi:app
"""

from __future__ import annotations

import os

import mongo_store
from api_server import app

# Warm up MongoDB before accepting requests (avoids SRV/dns import races).
try:
    mongo_store.warmup()
except Exception:
    # Logged inside warmup(); allow boot so health checks still respond.
    pass

# Only start the daily-report scheduler on the API process when explicitly
# enabled. Keep this false on Render's web service; use a worker for reports.
if os.getenv("REPORT_SCHEDULER_ON_API", "false").lower() in ("1", "true", "yes", "on"):
    from reports import scheduler

    scheduler.start(run_catch_up=os.getenv("REPORT_CATCHUP_ON_START", "false").lower() in ("1", "true", "yes", "on"))

if __name__ == "__main__":
    app.run()
