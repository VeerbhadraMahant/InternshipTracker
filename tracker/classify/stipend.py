"""Extracts pay and normalizes it to INR per month.

Structured ATS compensation fields are trusted. Numbers in free text are only
accepted when a pay period or a pay word (stipend, salary, pay, ...) is nearby,
so "$20M Series B" never becomes a stipend.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..models import Job

# Approximate rates, INR per unit. Good enough to rank and filter; the original
# figure is always shown next to the converted one.
INR_PER = {"INR": 1.0, "USD": 88.0, "EUR": 103.0, "GBP": 118.0, "CAD": 63.0, "AUD": 58.0, "SGD": 68.0}
HOURS_PER_MONTH = 160

_CUR = (r"(?P<cur>₹|Rs\.?|INR|US\$|USD|\$|€|EUR|£|GBP|CA\$|C\$|CAD|A\$|AUD|S\$|SGD)")
_NUM = r"(?P<{n}>\d{{1,3}}(?:,\d{{2,3}})+|\d+(?:\.\d+)?)\s*(?P<{n}m>k|K|lakhs?|lacs?|L)?"
_PERIOD = (r"(?P<period>per hour|an hour|/\s?h(?:ou)?r|hourly|p/?h|per month|a month|/\s?mo(?:nth)?|monthly|"
           r"p\.?m\.?|per annum|per year|a year|/\s?y(?:ea)?r|annually|yearly|p\.?a\.?|LPA)\b")
_AMOUNT = re.compile(
    rf"{_CUR}\s?{_NUM.format(n='lo')}(?:\s*(?:-|–|—|to)\s*{_CUR.replace('cur', 'cur2')}?\s?{_NUM.format(n='hi')})?"
    rf"(?:\s*(?:/|per|a|an)?\s*{_PERIOD})?",
)
_LPA = re.compile(rf"(?P<lo>\d+(?:\.\d+)?)\s*(?:-|to|–)?\s*(?P<hi>\d+(?:\.\d+)?)?\s*(?P<period>LPA|lpa)\b")
_PAY_WORD = re.compile(r"\b(stipend|salary|compensation|pay|paid|remuneration|ctc|rate|wage)\b", re.I)
_FUNDING = re.compile(r"^\s*(m|mm|million|b|bn|billion|in funding|raised|series|valuation|arr|revenue)\b", re.I)
_UNPAID = re.compile(r"\b(unpaid|no stipend|without stipend|voluntary position)\b", re.I)

_CUR_CODE = {"₹": "INR", "Rs": "INR", "Rs.": "INR", "$": "USD", "US$": "USD", "€": "EUR", "£": "GBP",
             "CA$": "CAD", "C$": "CAD", "A$": "AUD", "S$": "SGD"}


@dataclass
class Stipend:
    inr_month: Optional[int]
    text: str


def _num(raw: str, mult: Optional[str]) -> float:
    value = float(raw.replace(",", ""))
    if mult:
        m = mult.lower()
        if m == "k":
            value *= 1_000
        elif m.startswith("la") or m == "l":
            value *= 100_000
    return value


def _period(raw: Optional[str], amount: float, currency: str) -> str:
    if raw:
        r = raw.lower().replace(" ", "")
        if "h" in r and "month" not in r:
            return "hour"
        if "mo" in r or r.startswith("p.m") or r == "pm":
            return "month"
        return "year"
    # No period stated: infer from magnitude.
    if currency == "INR":
        return "year" if amount >= 150_000 else "month"
    if amount < 200:
        return "hour"
    return "year" if amount >= 15_000 else "month"


def _to_inr_month(amount: float, currency: str, period: str) -> int:
    inr = amount * INR_PER.get(currency, INR_PER["USD"])
    if period == "hour":
        inr *= HOURS_PER_MONTH
    elif period == "year":
        inr /= 12
    return int(round(inr))


def _from_text(text: str, trusted: bool) -> Optional[Stipend]:
    for m in _LPA.finditer(text):
        lo = float(m.group("lo")) * 100_000
        return Stipend(_to_inr_month(lo, "INR", "year"), m.group(0).strip())
    for m in _AMOUNT.finditer(text):
        if _FUNDING.match(text[m.end():m.end() + 20]):
            continue
        context = text[max(0, m.start() - 80):m.end() + 20]
        if not trusted and not (m.group("period") or _PAY_WORD.search(context)):
            continue
        currency = _CUR_CODE.get(m.group("cur"), m.group("cur").upper().rstrip("."))
        if currency == "RS":
            currency = "INR"
        lo = _num(m.group("lo"), m.group("lom"))
        if lo <= 0:
            continue
        period = _period(m.group("period"), lo, currency)
        return Stipend(_to_inr_month(lo, currency, period), m.group(0).strip())
    return None


def extract_stipend(job: Job) -> Stipend:
    if job.compensation:
        found = _from_text(job.compensation, trusted=True)
        if found:
            return found
    desc = job.description[:10000]
    found = _from_text(desc, trusted=False)
    if found:
        return found
    if _UNPAID.search(desc):
        return Stipend(0, "Unpaid")
    return Stipend(None, "")
