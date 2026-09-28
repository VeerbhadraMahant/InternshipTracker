"""Ashby public job posting API: https://developers.ashbyhq.com/docs/public-job-posting-api"""
from __future__ import annotations

from ..config import Company
from ..http import get_json
from ..models import Job, strip_html

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"


def parse(payload: dict, company: Company) -> list[Job]:
    jobs = []
    for j in payload.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locations = [j["location"]] if j.get("location") else []
        for sec in j.get("secondaryLocations") or []:
            if sec.get("location"):
                locations.append(sec["location"])
        comp = j.get("compensation") or {}
        comp_text = comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary")
        tags = list(company.tags)
        if j.get("employmentType"):
            tags.append(j["employmentType"])
        jobs.append(Job(
            source="ashby",
            company=company.name,
            title=(j.get("title") or "").strip(),
            url=j.get("jobUrl") or j.get("applyUrl", ""),
            native_id=j.get("id", ""),
            locations=locations,
            remote=bool(j.get("isRemote")) or j.get("workplaceType") == "Remote",
            description=j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")),
            posted_at=j.get("publishedAt"),
            compensation=comp_text,
            tags=tags,
        ))
    return jobs


def fetch(company: Company) -> list[Job]:
    return parse(get_json(API.format(slug=company.slug)), company)
