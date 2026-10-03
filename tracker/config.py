"""Loads config/watchlist.yaml and config/filters.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import re

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


@dataclass
class Company:
    name: str
    ats: str                       # greenhouse | lever | ashby | smartrecruiters | workday | careerpage
    slug: str = ""                 # board token / company id / workday tenant (unused for careerpage)
    site: str = ""                 # workday career site name
    host: str = ""                 # workday host, e.g. "nvidia.wd5.myworkdayjobs.com"
    url: str = ""                  # careerpage: the careers page Firecrawl reads
    location: str = ""             # careerpage: location to assume when a listing doesn't say
    tags: list[str] = field(default_factory=list)
    discovered: str = ""           # date added by tracker.discover, empty for hand-picked entries

    @property
    def key(self) -> str:
        """Stable scope id, e.g. "greenhouse:stripe" or "careerpage:persistent-systems"."""
        ident = self.slug or re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return f"{self.ats}:{ident}"


@dataclass
class Filters:
    locations: list[str] = field(default_factory=lambda: ["pune", "mumbai", "remote"])
    fields: list[str] = field(default_factory=lambda: ["software", "ai-ml", "data"])
    eligibility: list[str] = field(default_factory=lambda: ["india-ok", "open-worldwide", "unknown"])
    min_stipend_inr_month: int = 0
    include_undisclosed_stipend: bool = True


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_watchlist(path: Path | None = None, discovered: Path | None = None) -> tuple[list[Company], dict[str, Any]]:
    """Hand-picked companies plus the ones tracker.discover added, without duplicates."""
    data = _load_yaml(path or CONFIG_DIR / "watchlist.yaml")
    companies = [Company(**c) for c in data.get("companies", []) or []]
    discovered = discovered or CONFIG_DIR / "discovered.yaml"
    if discovered.exists():
        known = {c.key for c in companies}
        for c in (_load_yaml(discovered).get("companies") or []):
            company = Company(**c)
            if company.key not in known:
                known.add(company.key)
                companies.append(company)
    feeds = data.get("feeds", {}) or {}
    return companies, feeds


def load_discovery(path: Path | None = None) -> dict[str, Any]:
    return _load_yaml(path or CONFIG_DIR / "watchlist.yaml").get("discovery", {}) or {}


def load_filters(path: Path | None = None) -> Filters:
    data = _load_yaml(path or CONFIG_DIR / "filters.yaml")
    return Filters(**data)
