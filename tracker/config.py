"""Loads config/watchlist.yaml and config/filters.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


@dataclass
class Company:
    name: str
    ats: str                       # greenhouse | lever | ashby | smartrecruiters | workday
    slug: str                      # board token / company id / workday tenant
    site: str = ""                 # workday career site name
    host: str = ""                 # workday host, e.g. "nvidia.wd5.myworkdayjobs.com"
    tags: list[str] = field(default_factory=list)


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


def load_watchlist(path: Path | None = None) -> tuple[list[Company], dict[str, Any]]:
    data = _load_yaml(path or CONFIG_DIR / "watchlist.yaml")
    companies = [Company(**c) for c in data.get("companies", [])]
    feeds = data.get("feeds", {}) or {}
    return companies, feeds


def load_filters(path: Path | None = None) -> Filters:
    data = _load_yaml(path or CONFIG_DIR / "filters.yaml")
    return Filters(**data)
