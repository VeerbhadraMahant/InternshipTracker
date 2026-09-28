"""Workday career sites expose a JSON endpoint behind every *.myworkdayjobs.com page.

Many MNCs with Pune/Mumbai offices recruit through Workday, so this is the main
route to India-located roles. Not an official public API: it can change or rate
limit without notice, so failures are isolated per company.
"""
from __future__ import annotations

from ..config import Company
from ..http import get_json, post_json
from ..models import Job, strip_html

SEARCH_TERMS = ("intern", "internship", "trainee")
PAGE = 20
MAX_RESULTS = 100


def _base(company: Company) -> str:
    return f"https://{company.host}/wday/cxs/{company.slug}/{company.site}"


def parse_list(payload: dict, company: Company) -> list[Job]:
    jobs = []
    for p in payload.get("jobPostings", []):
        path = p.get("externalPath", "")
        if not path:
            continue
        jobs.append(Job(
            source="workday",
            company=company.name,
            title=(p.get("title") or "").strip(),
            url=f"https://{company.host}/{company.site}{path}",
            native_id=path.rsplit("/", 1)[-1],
            locations=[p["locationsText"]] if p.get("locationsText") else [],
            tags=list(company.tags),
        ))
    return jobs


def apply_detail(job: Job, payload: dict) -> None:
    info = payload.get("jobPostingInfo") or {}
    job.description = strip_html(info.get("jobDescription"))
    locs = [info.get("location")] + list(info.get("additionalLocations") or [])
    locs = [l for l in locs if l]
    if locs:
        job.locations = locs
    if (info.get("remoteType") or "").lower().startswith("remote"):
        job.remote = True
    job.posted_at = info.get("startDate") or job.posted_at
    if info.get("externalUrl"):
        job.url = info["externalUrl"]


def fetch(company: Company) -> list[Job]:
    seen: dict[str, tuple[Job, str]] = {}
    for term in SEARCH_TERMS:
        for offset in range(0, MAX_RESULTS, PAGE):
            payload = post_json(f"{_base(company)}/jobs", {
                "appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": term,
            })
            postings = payload.get("jobPostings", [])
            for job, raw in zip(parse_list(payload, company), (p for p in postings if p.get("externalPath"))):
                seen.setdefault(job.native_id, (job, raw["externalPath"]))
            if len(postings) < PAGE or offset + PAGE >= payload.get("total", 0):
                break
    for job, path in seen.values():
        try:
            apply_detail(job, get_json(f"{_base(company)}{path}"))
        except Exception:  # keep the list-level record
            pass
    return [job for job, _ in seen.values()]
