"""Legacy shim — re-exports from pipeline.runner for backward compatibility."""
# ruff: noqa: F401,F403

from pipeline.runner import *  # noqa: F401,F403
from pipeline.runner import (
    configure_logging,
    run_combined_cycle,
    run_forever,
    main,
)

# Re-export sub-cycle runners so tests can patch them here
from run_lokal_analysis import run_cycle as run_lokal_cycle  # noqa: F401
from run_sakshi_analysis import run_cycle as run_sakshi_cycle  # noqa: F401
from run_youtube_analysis import run_cycle as run_youtube_cycle  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
