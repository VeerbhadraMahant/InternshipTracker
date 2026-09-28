"""Discord webhook alerts (secret: DISCORD_WEBHOOK_URL)."""
from __future__ import annotations

import os
import time

from ..http import session
from ..models import Job

VERMILLION = 0xE42B0C
EMBEDS_PER_MESSAGE = 10


def configured() -> bool:
    return bool(os.environ.get("DISCORD_WEBHOOK_URL"))


def _embed(job: Job) -> dict:
    from . import ELIGIBILITY_LABEL, format_stipend

    where = " · ".join(job.locations[:2]) or ("Remote" if "remote" in job.location_tags else "Not stated")
    fields = [
        {"name": "Where", "value": where[:200], "inline": True},
        {"name": "Eligibility", "value": f"{ELIGIBILITY_LABEL.get(job.eligibility, job.eligibility)}"
                                         f"{': ' + job.eligibility_detail if job.eligibility_detail else ''}"[:200],
         "inline": True},
        {"name": "Stipend", "value": format_stipend(job)[:200], "inline": True},
    ]
    return {
        "title": f"{job.company}: {job.title}"[:250],
        "url": job.url,
        "color": VERMILLION,
        "fields": fields,
        "footer": {"text": f"{job.source} · {', '.join(job.fields)}"},
        "timestamp": job.first_seen,
    }


def send(jobs: list[Job], dashboard_url: str = "") -> None:
    url = os.environ["DISCORD_WEBHOOK_URL"]
    for i in range(0, len(jobs), EMBEDS_PER_MESSAGE):
        chunk = jobs[i:i + EMBEDS_PER_MESSAGE]
        content = ""
        if i == 0:
            content = f"**{len(jobs)} new internship{'s' if len(jobs) != 1 else ''}**"
            if dashboard_url:
                content += f" · <{dashboard_url}>"
        resp = session().post(url, json={"content": content, "embeds": [_embed(j) for j in chunk]}, timeout=20)
        resp.raise_for_status()
        time.sleep(1)  # stay well under Discord's webhook rate limit
