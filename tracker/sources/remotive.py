"""Remotive public API (https://remotive.com/api/remote-jobs). Remotive asks clients
not to poll more than a few times a day, so watchlist.yaml sets min_interval_hours."""
from __future__ import annotations

from ..http import get_json
from ..models import Job, strip_html

API = "https://remotive.com/api/remote-jobs?category={category}"


def parse(payload: dict) -> list[Job]:
    jobs = []
    for p in payload.get("jobs", []):
        tags = list(p.get("tags") or [])
        if p.get("job_type"):
            tags.append(p["job_type"])
        jobs.append(Job(
            source="remotive",
            company=(p.get("company_name") or "").strip(),
            title=(p.get("title") or "").strip(),
            url=p.get("url", ""),
            native_id=str(p.get("id")),
            locations=[p["candidate_required_location"]] if p.get("candidate_required_location") else [],
            remote=True,
            description=strip_html(p.get("description")),
            posted_at=p.get("publication_date"),
            compensation=p.get("salary") or None,
            tags=tags,
        ))
    return jobs


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for category in cfg.get("categories", ["software-dev"]):
        jobs.extend(parse(get_json(API.format(category=category))))
    return jobs
