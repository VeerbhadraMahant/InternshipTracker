"""Amazon's public job search JSON (the endpoint amazon.jobs itself calls).

Its location parameter is ignored, so this pages through every internship hit and keeps
the ones whose country_code is India.
"""
from __future__ import annotations

from ..config import Company
from ..http import get_json
from ..models import Job, strip_html

API = "https://www.amazon.jobs/en/search.json?base_query={query}&result_limit={limit}&offset={offset}&sort=recent"
QUERIES = ("intern",)
PAGE = 100
MAX_PAGES = 10
COUNTRIES = {"IND"}


def parse(payload: dict, company: Company) -> list[Job]:
    jobs = []
    for p in payload.get("jobs", []):
        if p.get("country_code") not in COUNTRIES:
            continue
        location = p.get("normalized_location") or p.get("location") or ""
        jobs.append(Job(
            source="amazon",
            company=company.name,
            title=(p.get("title") or "").strip(),
            url=f"https://www.amazon.jobs{p.get('job_path', '')}",
            native_id=str(p.get("id_icims") or p.get("id")),
            locations=[location] if location else [],
            description=strip_html(p.get("description") or p.get("description_short")),
            posted_at=p.get("posted_date"),
            tags=list(company.tags) + [t for t in (p.get("job_category"),) if t],
        ))
    return jobs


def fetch(company: Company) -> list[Job]:
    seen: dict[str, Job] = {}
    for query in QUERIES:
        for page in range(MAX_PAGES):
            payload = get_json(API.format(query=query, limit=PAGE, offset=page * PAGE))
            for job in parse(payload, company):
                seen.setdefault(job.native_id, job)
            if (page + 1) * PAGE >= int(payload.get("hits") or 0) or not payload.get("jobs"):
                break
    return list(seen.values())
