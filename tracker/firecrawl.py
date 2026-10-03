"""Minimal Firecrawl v2 client with a monthly credit budget.

Firecrawl bills credits (free tier: 1,000 a month). Scrape costs 1 credit per page, JSON
extraction adds 4, and search costs 2 credits per 10 results. Every call goes through
`_spend`, which refuses work that would push the month past FIRECRAWL_MONTHLY_BUDGET,
so a busy month degrades to "skipped" instead of failing runs on an empty balance.

State (credits this month, last content hash per career page) lives in
data/firecrawl_state.json and is committed with the rest of the data.
"""
from __future__ import annotations

import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import DATA_DIR
from .http import session

API = "https://api.firecrawl.dev/v2"
DEFAULT_BUDGET = 900
STATE_FILE = DATA_DIR / "firecrawl_state.json"
# Free plan allows 2 concurrent browsers; more parallel calls just queue or get 429s.
_CONCURRENCY = threading.BoundedSemaphore(2)


class SourceSkipped(Exception):
    """A source deliberately did no work this run (no key, budget reached, page unchanged)."""


class BudgetExceeded(SourceSkipped):
    pass


def _month(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


class FirecrawlState:
    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self._lock = threading.Lock()
        data: dict[str, Any] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        self.month: str = data.get("month", _month())
        self.credits_used: int = data.get("credits_used", 0)
        self.pages: dict[str, dict] = data.get("pages", {})
        self._roll_month()

    def _roll_month(self) -> None:
        if self.month != _month():
            self.month, self.credits_used = _month(), 0

    def reserve(self, credits: int, budget: int) -> None:
        with self._lock:
            self._roll_month()
            if self.credits_used + credits > budget:
                raise BudgetExceeded(f"Firecrawl monthly budget reached ({self.credits_used}/{budget} credits)")
            self.credits_used += credits

    def adjust(self, delta: int) -> None:
        with self._lock:
            self.credits_used = max(0, self.credits_used + delta)

    def page_hash(self, url: str) -> Optional[str]:
        return (self.pages.get(url) or {}).get("hash")

    def set_page_hash(self, url: str, digest: str) -> None:
        with self._lock:
            self.pages[url] = {"hash": digest, "changed": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"month": self.month, "credits_used": self.credits_used, "pages": dict(sorted(self.pages.items()))}
        self.path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


class Firecrawl:
    def __init__(self, api_key: str, state: FirecrawlState, budget: int = DEFAULT_BUDGET):
        self.api_key, self.state, self.budget = api_key, state, budget

    def _post(self, path: str, body: dict, estimate: int) -> dict:
        self.state.reserve(estimate, self.budget)
        try:
            with _CONCURRENCY:
                resp = session().post(f"{API}/{path}", json=body, timeout=90,
                                      headers={"Authorization": f"Bearer {self.api_key}"})
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            self.state.adjust(-estimate)  # failed calls aren't billed
            raise
        if not payload.get("success", True):
            raise RuntimeError(f"Firecrawl error: {payload.get('error') or payload}")
        actual = payload.get("creditsUsed")
        if actual is None:
            actual = ((payload.get("data") or {}).get("metadata") or {}).get("creditsUsed") \
                if isinstance(payload.get("data"), dict) else None
        if isinstance(actual, (int, float)):
            self.state.adjust(int(actual) - estimate)
        return payload

    def scrape(self, url: str, json_schema: Optional[dict] = None, prompt: str = "") -> dict:
        """Markdown + links (1 credit), or JSON extraction (5 credits) when a schema is given."""
        if json_schema:
            formats: list = [{"type": "json", "schema": json_schema, "prompt": prompt}]
            estimate = 5
        else:
            formats, estimate = ["markdown", "links"], 1
        body = {"url": url, "formats": formats, "onlyMainContent": True, "waitFor": 1500,
                "removeBase64Images": True}
        return self._post("scrape", body, estimate).get("data") or {}

    def search(self, query: str, limit: int = 20) -> list[dict]:
        body = {"query": query, "limit": limit, "sources": [{"type": "web"}]}
        data = self._post("search", body, 2 * math.ceil(limit / 10)).get("data") or {}
        return data.get("web", []) if isinstance(data, dict) else data


_client: Optional[Firecrawl] = None
_client_lock = threading.Lock()


def client() -> Firecrawl:
    """Shared client for this process. Raises SourceSkipped when no key is configured."""
    global _client
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        raise SourceSkipped("no FIRECRAWL_API_KEY configured")
    with _client_lock:
        if _client is None:
            budget = int(os.environ.get("FIRECRAWL_MONTHLY_BUDGET", DEFAULT_BUDGET))
            _client = Firecrawl(key, FirecrawlState(), budget)
        return _client


def summary() -> Optional[dict]:
    """Credit usage for status.json, or None if Firecrawl wasn't used this run."""
    if _client is None:
        return None
    return {"month": _client.state.month, "credits_used": _client.state.credits_used, "budget": _client.budget}


def save_state() -> None:
    if _client is not None:
        _client.state.save()
