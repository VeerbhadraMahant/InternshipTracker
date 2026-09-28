"""Shared HTTP session with timeouts and retry/backoff."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 25
USER_AGENT = "InternshipTracker/1.0 (+https://github.com/VeerbhadraMahant/InternshipTracker; personal job watcher)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers["User-Agent"] = USER_AGENT
        _session = s
    return _session


def get_json(url: str, **kwargs):
    resp = session().get(url, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


def post_json(url: str, payload: dict, **kwargs):
    resp = session().post(url, json=payload, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_text(url: str, **kwargs) -> str:
    resp = session().get(url, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.text
