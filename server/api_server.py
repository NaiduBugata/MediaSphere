"""Legacy shim — re-exports from api.app for backward compatibility."""
# ruff: noqa: F401,F403,E402

from api.app import app, _start_scheduler  # noqa: F401

if __name__ == "__main__":
    import os

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "5000"))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    app.debug = debug
    _start_scheduler()
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
