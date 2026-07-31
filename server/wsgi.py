"""WSGI entry point for production servers (gunicorn / waitress / uWSGI).

Exposes the Flask ``app``. By default the API web service does NOT start the
report scheduler or send emails — those belong on a separate worker process.

Run with, e.g.:
    gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 wsgi:app
"""

from __future__ import annotations

import atexit
import os

import mongo_store
from api.app import app

# Warm up MongoDB before accepting requests (avoids SRV/dns import races).
_mongo_ok = False
try:
    mongo_store.warmup()
    _mongo_ok = True
except Exception:
    pass


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _notify_startup() -> None:
    try:
        from notifications import get_notification_manager

        get_notification_manager().notify_startup(
            {
                "Collectors Loaded": "yes",
                "Scheduler Running": "yes" if _flag("PIPELINE_ON_API") or _flag("REPORT_SCHEDULER_ON_API") else "no",
                "Mongo Connected": "yes" if _mongo_ok else "no",
                "Notification Services Ready": "yes",
            },
            async_=True,
        )
    except Exception:
        pass


def _notify_shutdown() -> None:
    try:
        from notifications import get_notification_manager

        get_notification_manager().notify_shutdown(async_=False)
    except Exception:
        pass


if _flag("REPORT_SCHEDULER_ON_API"):
    from reports import scheduler

    scheduler.start(run_catch_up=_flag("REPORT_CATCHUP_ON_START"))

if _flag("PIPELINE_ON_API"):
    import pipeline_scheduler

    pipeline_scheduler.start(run_catch_up=_flag("PIPELINE_CATCHUP_ON_START", "true"))

_notify_startup()
atexit.register(_notify_shutdown)

if __name__ == "__main__":
    app.run()
