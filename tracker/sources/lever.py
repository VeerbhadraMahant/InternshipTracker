"""Lever public postings API: https://github.com/lever/postings-api"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import Company
from ..http import get_json
from ..models import Job, strip_html

API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def _salary(sr: dict | None) -> str | None:
    if not sr or not (sr.get("min") or sr.get("max")):
        return None
    interval = (sr.get("interval") or "").replace("-", " ")
    return f"{sr.get('currency', '')} {sr.get('min')} - {sr.get('max')} {interval}".strip()


def parse(payload: list, company: Company) -> list[Job]:
    jobs = []
    for p in payload:
        cats = p.get("categories") or {}
        locations = list(cats.get("allLocations") or ([cats["location"]] if cats.get("location") else []))
        parts = [p.get("descriptionPlain") or strip_html(p.get("description"))]
        for lst in p.get("lists") or []:
            parts.append(f"{lst.get('text', '')}: {strip_html(lst.get('content'))}")
        parts.append(p.get("additionalPlain") or strip_html(p.get("additional")))
        created = p.get("createdAt")
        jobs.append(Job(
            source="lever",
            company=company.name,
            title=(p.get("text") or "").strip(),
            url=p.get("hostedUrl", ""),
            native_id=p.get("id", ""),
            locations=locations,
            remote=(p.get("workplaceType") == "remote"),
            description="\n".join(x for x in parts if x),
            posted_at=datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else None,
            compensation=_salary(p.get("salaryRange")),
            tags=list(company.tags) + ([cats["commitment"]] if cats.get("commitment") else []),
        ))
    return jobs


def fetch(company: Company) -> list[Job]:
    return parse(get_json(API.format(slug=company.slug)), company)
