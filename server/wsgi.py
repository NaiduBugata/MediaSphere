"""WSGI entry point for production servers (gunicorn / waitress / uWSGI).

Exposes the Flask ``app`` and starts the daily-report scheduler once at import
time (the ``__main__`` block in api_server.py does not run under a WSGI server).

Run with, e.g.:
    gunicorn --workers 1 --bind 0.0.0.0:5000 wsgi:app

Keep the API to a single worker when REPORT_ENABLED=true so exactly one
scheduler instance runs. De-duplication (daily_reports.report_date) still
protects against duplicate emails if multiple workers are used.
"""

from __future__ import annotations

from api_server import app, scheduler

# Boot the daily-report scheduler (07:00 IST + missed-run catch-up).
scheduler.start()

if __name__ == "__main__":
    app.run()
