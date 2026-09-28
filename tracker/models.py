"""Normalized job record shared by every source, classifier and the dashboard."""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: Optional[str]) -> str:
    """Turn an HTML fragment (possibly entity-escaped twice, as Greenhouse does) into plain text."""
    if not text:
        return ""
    text = html.unescape(html.unescape(text))
    text = re.sub(r"<\s*(br|/p|/li|/div|/h\d)\s*/?>", "\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def make_id(source: str, company: str, native_id: str) -> str:
    raw = f"{source}|{company}|{native_id}".lower()
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


@dataclass
class Job:
    source: str                     # "greenhouse", "remoteok", ...
    company: str
    title: str
    url: str
    native_id: str
    locations: list[str] = field(default_factory=list)
    remote: bool = False            # the source explicitly flags the role as remote
    description: str = ""           # plain text, truncated
    posted_at: Optional[str] = None # ISO-8601 if the source provides it
    compensation: Optional[str] = None  # raw compensation text from structured ATS fields
    tags: list[str] = field(default_factory=list)

    # Filled by the runner / store
    scope: str = ""                 # fetch unit this came from, e.g. "greenhouse:stripe" or "remoteok"
    id: str = ""
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    status: str = "open"            # open | closed
    missed_runs: int = 0

    # Filled by classifiers
    is_internship: bool = False
    fields: list[str] = field(default_factory=list)       # software, ai-ml, data
    location_tags: list[str] = field(default_factory=list)  # pune, mumbai, india, remote, other
    eligibility: str = "unknown"    # open-worldwide | india-ok | restricted | needs-work-auth | unknown | onsite
    eligibility_detail: str = ""    # e.g. "US only" / "UTC-5..UTC+1"
    eligibility_evidence: str = ""  # the phrase the classifier matched
    stipend_inr_month: Optional[int] = None
    stipend_text: str = ""          # human-readable original, e.g. "$25/hr"

    def __post_init__(self) -> None:
        if not self.id:
            self.id = make_id(self.source, self.company, self.native_id)

    def text_blob(self) -> str:
        return f"{self.title}\n{' / '.join(self.locations)}\n{self.compensation or ''}\n{self.description}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
