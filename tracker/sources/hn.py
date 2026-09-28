"""Hacker News "Ask HN: Who is hiring?" monthly thread, via the Algolia HN API.

Comments follow a loose convention: "Company | Role(s) | Location | REMOTE/ONSITE | ...".
Only top-level comments that mention interns are kept, the rest are full-time roles.
"""
from __future__ import annotations

import re

from ..http import get_json
from ..models import Job, strip_html

SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10"
ITEM = "https://hn.algolia.com/api/v1/items/{id}"
_INTERN = re.compile(r"\bintern(s|ship|ships)?\b", re.I)


def latest_thread_id(payload: dict) -> str | None:
    for hit in payload.get("hits", []):
        if (hit.get("title") or "").lower().startswith("ask hn: who is hiring"):
            return hit.get("objectID")
    return None


def parse_thread(payload: dict) -> list[Job]:
    jobs = []
    for c in payload.get("children", []):
        text = strip_html(c.get("text"))
        if not text or not _INTERN.search(text):
            continue
        header = text.split("\n", 1)[0][:300]
        parts = [p.strip() for p in header.split("|")]
        company = parts[0][:80] if parts else "HN poster"
        role = next((p for p in parts[1:] if _INTERN.search(p)), None)
        title = role or "Internship (see post)"
        location_bits = [p for p in parts[1:] if p is not role and len(p) < 60]
        jobs.append(Job(
            source="hn-whoishiring",
            company=company,
            title=title[:140],
            url=f"https://news.ycombinator.com/item?id={c.get('id')}",
            native_id=str(c.get("id")),
            locations=location_bits[:3],
            remote=bool(re.search(r"\bremote\b", header, re.I)),
            description=text,
            posted_at=c.get("created_at"),
        ))
    return jobs


def fetch(cfg: dict) -> list[Job]:
    thread = latest_thread_id(get_json(SEARCH))
    if not thread:
        return []
    return parse_thread(get_json(ITEM.format(id=thread)))
