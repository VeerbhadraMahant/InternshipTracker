"""RemoteOK public API (https://remoteok.com/api). Their terms ask API users to link
back to the listing URL, which the dashboard does for every job."""
from __future__ import annotations

from ..http import get_json
from ..models import Job, strip_html

API = "https://remoteok.com/api"


def parse(payload: list) -> list[Job]:
    jobs = []
    for p in payload:
        if not isinstance(p, dict) or "id" not in p or not p.get("position"):
            continue  # first element is a legal notice
        salary = None
        if p.get("salary_min") or p.get("salary_max"):
            salary = f"USD {p.get('salary_min') or ''} - {p.get('salary_max') or ''} per year"
        jobs.append(Job(
            source="remoteok",
            company=(p.get("company") or "").strip(),
            title=p["position"].strip(),
            url=p.get("url") or f"https://remoteok.com/remote-jobs/{p['id']}",
            native_id=str(p["id"]),
            locations=[p["location"]] if p.get("location") else [],
            remote=True,
            description=strip_html(p.get("description")),
            posted_at=p.get("date"),
            compensation=salary,
            tags=list(p.get("tags") or []),
        ))
    return jobs


def fetch(cfg: dict) -> list[Job]:
    return parse(get_json(API))
