"""Environment-driven configuration for the Lokal collector."""

from __future__ import annotations

import os

# Combined pipeline interval (Lokal + YouTube worker). Override via env on Render/local.
PIPELINE_INTERVAL_HOURS = float(os.getenv("PIPELINE_INTERVAL_HOURS", "1"))
CHECK_INTERVAL = int(PIPELINE_INTERVAL_HOURS * 60 * 60)
