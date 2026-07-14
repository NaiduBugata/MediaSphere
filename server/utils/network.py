"""HTTP session factory and network helpers."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_http_session(
    *,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    user_agent: str = "Mozilla/5.0 (compatible; MediaSphere/1.0)",
    headers: dict[str, str] | None = None,
) -> requests.Session:
    """Create a requests Session with retry strategy and default headers."""
    session = requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=list(status_forcelist),
        allowed_methods=["GET", "HEAD", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    default_headers = {"User-Agent": user_agent, "Accept": "application/json"}
    if headers:
        default_headers.update(headers)
    session.headers.update(default_headers)
    return session
