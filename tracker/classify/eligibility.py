"""Can a student in India actually take this role?

Deliberately conservative: a remote role is only called open when the text says so.
Silence is "unknown", never "open". Every verdict carries the phrase it was based on.

Verdicts:
  india-ok        located in India, or remote with India / IST / APAC explicitly allowed
  open-worldwide  remote and explicitly worldwide / anywhere, with no restriction found
  timezone        remote but must work hours that don't include IST (UTC+5:30)
  needs-work-auth remote but requires work authorization / citizenship / no sponsorship
  restricted      remote but limited to specific countries or regions that exclude India
  onsite-abroad   on-site or hybrid outside India
  unknown         remote with no statement either way
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Job

IST = 5.5

# Case-sensitive abbreviations so "us"/"eu" in prose don't match.
_REGION_ABBR = r"US|USA|U\.S\.A?\.?|UK|U\.K\.|EU|EMEA|LATAM"
_REGION_WORDS = (r"united states|america|americas|north america|canada|united kingdom|england|europe|"
                 r"european union|germany|france|spain|netherlands|poland|portugal|ireland|italy|sweden|"
                 r"switzerland|brazil|latin america|mexico|argentina|colombia|australia|new zealand|japan|"
                 r"philippines|israel|nigeria|kenya|south africa|singapore|uae")
_INDIA_OK = re.compile(r"\b(india|indian|IST|asia|APAC|asia[- ]pacific|south asia)\b", re.I)
_WORLDWIDE = re.compile(
    r"\b(worldwide|anywhere( in the world)?|global(ly)?( remote)?|any (country|location|timezone)|"
    r"all (countries|time ?zones)|work from anywhere|fully distributed|location[- ]independent)\b", re.I)
_REGION_IN_LOCATION = re.compile(rf"(?:\b(?:{_REGION_ABBR})\b)|(?i:\b(?:{_REGION_WORDS})\b)")

# Known regions only; the looser form also accepts any capitalised place name.
_WHERE_KNOWN = rf"(?P<where>(?:the )?(?:(?:{_REGION_ABBR})\b|(?i:{_REGION_WORDS}|india)\b))"
_WHERE = rf"(?P<where>(?:the )?(?:(?:{_REGION_ABBR})\b|(?i:{_REGION_WORDS}|india)\b|[A-Z][a-z]+(?: [A-Z][a-z]+)?))"
_RESTRICT_PATTERNS = [
    re.compile(rf"(?i:must|should|need to|required to|have to)(?: currently)? (?i:be )?(?i:located|based|residing|"
               rf"resident|reside|living|live)(?: (?i:in|within))? {_WHERE}"),
    re.compile(rf"(?i:(?:open |available )?only(?: to)?|exclusively)(?: (?i:open to|accepting|hiring|considering))?(?: (?i:candidates|applicants|"
               rf"people|residents))?(?: (?i:who are))?(?: (?i:located|based))? (?i:in|from|within) {_WHERE_KNOWN}"),
    re.compile(rf"(?P<where>{_REGION_ABBR}|(?i:{_REGION_WORDS}))[- ](?i:only|based candidates|residents only)\b"),
    re.compile(rf"(?i:open to|available to) (?i:candidates|applicants|residents) (?i:in|of|from) {_WHERE_KNOWN}(?: (?i:only))"),
]
_AUTH_PATTERNS = [
    re.compile(rf"(?i:legally )?(?i:authori[sz]ed|eligible|permitted) to work in {_WHERE}"),
    re.compile(r"(?i:\b(?:not able to|unable to|cannot|can't|can not|do not|don't|won't|will not|are not able to)"
               r"(?: currently)?(?: provide| offer)?(?: visa)? sponsor)"),
    re.compile(r"(?i:\b(?:no|without) (?:visa )?sponsorship)"),
    re.compile(r"(?i:\b(?:us|u\.s\.) (?:citizen(?:ship)?|person)s?\b|security clearance|green card)"),
    re.compile(r"(?i:\bwork authori[sz]ation\b)"),
]
_TZ_RANGE = re.compile(
    r"(?i:UTC|GMT)\s?(?P<a>[+\-−–]\s?\d{1,2}(?::?\d{2})?)?\s*(?:to|-|–|—|and|through|until)\s*"
    r"(?i:UTC|GMT)?\s?(?P<b>[+\-−–]\s?\d{1,2}(?::?\d{2})?)")
_TZ_NAMED = re.compile(
    r"(?i:overlap|within|aligned?|align with|during|compatible with|work(?:ing)? (?:in|during|within))"
    r"[^.\n]{0,40}?\b(?P<tz>(?:US|U\.S\.|North American|American|Pacific|Eastern|Central|Mountain|European|"
    r"EU|UK|CET|CEST|GMT|BST|PST|PDT|PT|EST|EDT|ET|CST|CDT|MST|IST|India|Indian|Asian|APAC)"
    r"(?: (?i:standard))?) ?(?i:time ?zones?|hours|business hours|working hours|time)\b")
_TZ_ASIA = re.compile(r"^(IST|India|Indian|Asian|APAC)", re.I)


@dataclass
class Verdict:
    label: str
    detail: str = ""
    evidence: str = ""


def _snippet(text: str, m: re.Match, pad: int = 50) -> str:
    start, end = max(0, m.start() - pad), min(len(text), m.end() + pad)
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


def _offset(raw: str) -> float:
    raw = raw.replace(" ", "").replace("−", "-").replace("–", "-")
    sign = -1 if raw.startswith("-") else 1
    raw = raw.lstrip("+-")
    if ":" in raw:
        h, m = raw.split(":")
    elif len(raw) > 2:
        h, m = raw[:-2], raw[-2:]
    else:
        h, m = raw, "0"
    return sign * (int(h) + int(m) / 60)


def _where_is_india(where: str) -> bool:
    return bool(_INDIA_OK.search(where))


def _check_restrictions(text: str) -> Verdict | None:
    for rx in _RESTRICT_PATTERNS:
        for m in rx.finditer(text):
            where = m.group("where").strip()
            if _where_is_india(where):
                return Verdict("india-ok", f"Open to {where}", _snippet(text, m))
            return Verdict("restricted", f"{where} only", _snippet(text, m))
    for m in _TZ_RANGE.finditer(text):
        if not m.group("a"):
            continue
        a, b = sorted((_offset(m.group("a")), _offset(m.group("b"))))
        if not a <= IST <= b:
            return Verdict("timezone", f"UTC{a:+g} to UTC{b:+g}", _snippet(text, m))
        return None
    for m in _TZ_NAMED.finditer(text):
        tz = m.group("tz")
        if _TZ_ASIA.match(tz):
            return Verdict("india-ok", f"{tz} hours", _snippet(text, m))
        return Verdict("timezone", f"{tz} hours", _snippet(text, m))
    for rx in _AUTH_PATTERNS:
        m = rx.search(text)
        if m:
            where = m.groupdict().get("where")
            if where and _where_is_india(where):
                return Verdict("india-ok", f"Work auth: {where}", _snippet(text, m))
            return Verdict("needs-work-auth", f"Work authorization{' in ' + where if where else ''} required",
                           _snippet(text, m))
    return None


def classify_eligibility(job: Job, location_tags: list[str]) -> Verdict:
    loc_text = " / ".join(job.locations)
    in_india = "india" in location_tags
    remote = "remote" in location_tags

    if in_india:
        where = "Pune" if "pune" in location_tags else "Mumbai" if "mumbai" in location_tags else "India"
        return Verdict("india-ok", f"{'Remote / ' if remote else ''}{where}", loc_text)
    if not remote:
        return Verdict("onsite-abroad", loc_text or "Location not stated", loc_text)

    # Structured location field first: "Remote - US", "Remote (APAC)", "Worldwide".
    m = _INDIA_OK.search(loc_text)
    if m:
        return Verdict("india-ok", loc_text, loc_text)
    region = _REGION_IN_LOCATION.search(loc_text)
    if region:
        return Verdict("restricted", f"{region.group(0)} only", loc_text)
    location_says_worldwide = bool(_WORLDWIDE.search(loc_text))

    # Description can override a "Worldwide" label: feeds often mislabel US-only roles.
    text = job.description[:8000]
    restriction = _check_restrictions(text)
    if restriction:
        return restriction
    if location_says_worldwide:
        return Verdict("open-worldwide", "Worldwide", loc_text)
    m = _WORLDWIDE.search(text)
    if m:
        return Verdict("open-worldwide", "Worldwide", _snippet(text, m))
    return Verdict("unknown", "No location restriction stated", "")
