"""Decides whether a posting is an internship / trainee role."""
from __future__ import annotations

import re

from ..models import Job

_POSITIVE = re.compile(
    r"\b(intern|interns|internship|internships|co-?op|apprentice(ship)?|trainee|"
    r"summer (analyst|associate|engineer|student|fellow)|student (developer|engineer|researcher)|"
    r"werkstudent|working student|placement student|industrial placement)\b",
    re.I,
)
_NEGATIVE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|vp|vice president|architect|"
    r"recruiter|coordinator|intern(ship)? (program )?(manager|coordinator|recruiter))\b",
    re.I,
)
_TAG_POSITIVE = re.compile(r"\bintern(ship)?\b", re.I)


def looks_like_internship_title(title: str) -> bool:
    return bool(_POSITIVE.search(title)) and not _NEGATIVE.search(title)


def is_internship(job: Job) -> bool:
    if _NEGATIVE.search(job.title):
        return False
    if _POSITIVE.search(job.title):
        return True
    # Structured employment type from the ATS/feed (Ashby "Intern", Remotive "internship", ...).
    return any(_TAG_POSITIVE.search(t) for t in job.tags)
