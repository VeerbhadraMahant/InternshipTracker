"""We Work Remotely category RSS feeds."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..http import get_text
from ..models import Job, strip_html

FEED = "https://weworkremotely.com/categories/{category}.rss"


def parse(xml_text: str) -> list[Job]:
    root = ET.fromstring(xml_text)
    jobs = []
    for item in root.iter("item"):
        raw_title = (item.findtext("title") or "").strip()
        company, _, title = raw_title.partition(":")
        if not title:
            company, title = "", raw_title
        pub = item.findtext("pubDate")
        try:
            posted = parsedate_to_datetime(pub).isoformat() if pub else None
        except (TypeError, ValueError):
            posted = None
        region = (item.findtext("region") or "").strip()
        link = (item.findtext("link") or "").strip()
        jobs.append(Job(
            source="weworkremotely",
            company=company.strip(),
            title=title.strip(),
            url=link,
            native_id=(item.findtext("guid") or link).strip(),
            locations=[region] if region else [],
            remote=True,
            description=strip_html(item.findtext("description")),
            posted_at=posted,
            tags=[(item.findtext("type") or "").strip()] if item.findtext("type") else [],
        ))
    return jobs


def fetch(cfg: dict) -> list[Job]:
    jobs: list[Job] = []
    for category in cfg.get("categories", ["remote-programming-jobs"]):
        jobs.extend(parse(get_text(FEED.format(category=category))))
    return jobs
