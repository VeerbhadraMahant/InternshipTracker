"""Greenhouse public job board API: https://developers.greenhouse.io/job-board.html"""
from __future__ import annotations

from ..config import Company
from ..http import get_json
from ..models import Job, strip_html

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def parse(payload: dict, company: Company) -> list[Job]:
    jobs = []
    for j in payload.get("jobs", []):
        locations = []
        if (j.get("location") or {}).get("name"):
            locations.append(j["location"]["name"])
        for office in j.get("offices") or []:
            name = office.get("location") or office.get("name")
            if name and name not in locations:
                locations.append(name)
        jobs.append(Job(
            source="greenhouse",
            company=company.name,
            title=j.get("title", "").strip(),
            url=j.get("absolute_url", ""),
            native_id=str(j.get("id")),
            locations=locations,
            description=strip_html(j.get("content")),
            posted_at=j.get("first_published") or j.get("updated_at"),
            tags=list(company.tags),
        ))
    return jobs


def fetch(company: Company) -> list[Job]:
    return parse(get_json(API.format(slug=company.slug)), company)
