"""Careers pages with no public job API (Darwinbox, SuccessFactors, Taleo, custom sites), via Firecrawl.

Cost per run: 1 credit to fetch the page as markdown. If the content hash matches last run the
source is skipped and its jobs stay as they are. If it changed, internship links are pulled out
of the markdown for free; only when the page mentions interns but no such links are found does
it pay 4 more credits for Firecrawl's LLM extraction.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin

from .. import firecrawl
from ..classify.internship import looks_like_internship_title
from ..config import Company
from ..models import Job

_LINK = re.compile(r"\[([^\]\n]{3,200})\]\((\S+?)(?:\s+\"[^\"]*\")?\)")
_INTERN = re.compile(r"\b(intern|internship|trainee|apprentice)", re.I)
_VOLATILE = re.compile(r"\b\d+\s+(minutes?|hours?|days?)\s+ago\b|\bposted (today|yesterday)\b", re.I)

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title"],
            },
        }
    },
    "required": ["jobs"],
}
JSON_PROMPT = ("List every open job posting on this careers page that is an internship, trainee or "
               "apprentice role. Use the posting's own link as url and its location as shown.")


def content_hash(markdown: str) -> str:
    # Relative dates ("3 days ago") change daily without the listings changing.
    return hashlib.sha256(_VOLATILE.sub("", markdown).encode()).hexdigest()[:20]


def _job(company: Company, title: str, url: str, location: str = "", context: str = "") -> Job:
    return Job(
        source="careerpage",
        company=company.name,
        title=title.strip()[:200],
        url=url,
        native_id=url if url != company.url else title.strip().lower(),
        locations=[location or company.location] if (location or company.location) else [],
        description=context[:1200],
        tags=list(company.tags),
    )


def extract_links(markdown: str, company: Company) -> list[Job]:
    jobs: dict[str, Job] = {}
    for line in markdown.splitlines():
        for m in _LINK.finditer(line):
            text, href = m.group(1).strip(" *_#"), m.group(2)
            if not looks_like_internship_title(text) or href.startswith(("mailto:", "#")):
                continue
            url = urljoin(company.url, href)
            jobs.setdefault(url, _job(company, text, url, context=line.strip()))
    return list(jobs.values())


def from_json(data: dict, company: Company) -> list[Job]:
    out = []
    for item in ((data.get("json") or {}).get("jobs") or []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        url = urljoin(company.url, item.get("url") or "") or company.url
        out.append(_job(company, title, url, item.get("location") or ""))
    return out


def fetch(company: Company) -> list[Job]:
    if not company.url:
        raise ValueError(f"careerpage entry {company.name!r} needs a url")
    fc = firecrawl.client()
    page = fc.scrape(company.url)
    markdown = page.get("markdown") or ""
    digest = content_hash(markdown)
    if fc.state.page_hash(company.url) == digest:
        raise firecrawl.SourceSkipped("unchanged")
    jobs = extract_links(markdown, company)
    if not jobs and _INTERN.search(markdown):
        jobs = from_json(fc.scrape(company.url, json_schema=JSON_SCHEMA, prompt=JSON_PROMPT), company)
    fc.state.set_page_hash(company.url, digest)
    return jobs
