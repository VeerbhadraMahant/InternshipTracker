"""SmartRecruiters public posting API: https://developers.smartrecruiters.com/docs/posting-api"""
from __future__ import annotations

from ..classify.internship import looks_like_internship_title
from ..config import Company
from ..http import get_json
from ..models import Job, strip_html

LIST_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}"
DETAIL_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings/{id}"
MAX_PAGES = 10


def _location(loc: dict) -> str:
    if loc.get("fullLocation"):
        return loc["fullLocation"]
    return ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)


def parse_list(payload: dict, company: Company) -> list[Job]:
    jobs = []
    for p in payload.get("content", []):
        loc = p.get("location") or {}
        tags = list(company.tags)
        for key in ("typeOfEmployment", "experienceLevel"):
            if (p.get(key) or {}).get("label"):
                tags.append(p[key]["label"])
        jobs.append(Job(
            source="smartrecruiters",
            company=company.name,
            title=(p.get("name") or "").strip(),
            url=f"https://jobs.smartrecruiters.com/{company.slug}/{p.get('id')}",
            native_id=str(p.get("id")),
            locations=[_location(loc)] if _location(loc) else [],
            remote=bool(loc.get("remote")),
            posted_at=p.get("releasedDate"),
            tags=tags,
        ))
    return jobs


def parse_detail(payload: dict) -> str:
    sections = ((payload.get("jobAd") or {}).get("sections")) or {}
    return "\n".join(strip_html((s or {}).get("text")) for s in sections.values() if s)


def fetch(company: Company) -> list[Job]:
    jobs: list[Job] = []
    for page in range(MAX_PAGES):
        payload = get_json(LIST_API.format(slug=company.slug, offset=page * 100))
        batch = parse_list(payload, company)
        jobs.extend(batch)
        if len(batch) < 100 or len(jobs) >= payload.get("totalFound", 0):
            break
    # Descriptions need one call per posting; only pay that for plausible internships.
    for job in jobs:
        if looks_like_internship_title(job.title) or any("intern" in t.lower() for t in job.tags):
            try:
                job.description = parse_detail(get_json(DETAIL_API.format(slug=company.slug, id=job.native_id)))
            except Exception:  # description is a nice-to-have; keep the posting
                pass
    return jobs
