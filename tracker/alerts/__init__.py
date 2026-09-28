"""Alert channels. Each is skipped silently when its secrets are not configured."""
from __future__ import annotations

import logging

from ..config import Filters
from ..models import Job
from . import discord, email

log = logging.getLogger(__name__)

ELIGIBILITY_LABEL = {
    "india-ok": "Open to India",
    "open-worldwide": "Worldwide",
    "unknown": "Eligibility unclear",
    "timezone": "Timezone-bound",
    "needs-work-auth": "Needs work auth",
    "restricted": "Region-restricted",
    "onsite-abroad": "On-site abroad",
}


def matches(job: Job, f: Filters) -> bool:
    if not job.is_internship or job.status != "open":
        return False
    if not set(job.location_tags) & set(f.locations):
        return False
    if not set(job.fields) & set(f.fields):
        return False
    if job.eligibility not in f.eligibility:
        return False
    if job.stipend_inr_month is None:
        return f.include_undisclosed_stipend
    return job.stipend_inr_month >= f.min_stipend_inr_month


def format_stipend(job: Job) -> str:
    if job.stipend_inr_month is None:
        return "Stipend not disclosed"
    if job.stipend_inr_month == 0:
        return "Unpaid"
    return f"≈ ₹{job.stipend_inr_month:,}/mo ({job.stipend_text})"


def send_all(jobs: list[Job], dashboard_url: str = "") -> dict[str, str]:
    results = {}
    for name, channel in (("discord", discord), ("email", email)):
        if not channel.configured():
            results[name] = "not configured"
            continue
        try:
            channel.send(jobs, dashboard_url)
            results[name] = f"sent {len(jobs)}"
        except Exception as exc:  # one channel failing must not block the other
            log.exception("%s alert failed", name)
            results[name] = f"error: {exc}"
    return results
