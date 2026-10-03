"""Find new companies to track: python -m tracker.discover [--dry-run]

Firecrawl search looks for internship postings on job boards whose public APIs the tracker
already reads for free (Greenhouse, Lever, Ashby, SmartRecruiters, Workday). Each new board is
checked against its API, and boards that answer with at least one posting go into
config/discovered.yaml. After that they cost no Firecrawl credits; only the search does
(2 credits per 10 results).
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import yaml

from . import firecrawl
from .config import CONFIG_DIR, Company, load_discovery, load_watchlist
from .sources import ATS

log = logging.getLogger("tracker.discover")

DEFAULT_QUERIES = [
    "site:jobs.lever.co intern India",
    "site:job-boards.greenhouse.io intern India",
    "site:boards.greenhouse.io intern Pune OR Mumbai",
    "site:jobs.ashbyhq.com intern India",
    "site:myworkdayjobs.com intern Pune",
    "site:myworkdayjobs.com intern Mumbai",
    "site:jobs.smartrecruiters.com intern Pune OR Mumbai",
    "site:jobs.ashbyhq.com OR site:jobs.lever.co software intern remote India",
]
DISCOVERED_FILE = CONFIG_DIR / "discovered.yaml"
HEADER = """\
# Companies found by `python -m tracker.discover` (weekly Discover workflow).
# Each one answered its job board's public API with at least one posting when it was added.
# Safe to edit: delete an entry to stop tracking it, or move it into watchlist.yaml to keep it
# permanently. Entries already in watchlist.yaml are never added here.
"""

_WORKDAY_HOST = re.compile(r"^([a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com$")
_WORKDAY_SITE_HOST = re.compile(r"^wd\d+\.myworkdaysite\.com$")
_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def _pretty(slug: str) -> str:
    return re.sub(r"[-_.]+", " ", slug).strip().title()


def _name_from_title(ats: str, title: str) -> Optional[str]:
    """Company name from a search result title, when the board's title format gives it away."""
    t = (title or "").strip()
    patterns = {
        "greenhouse": r"\bat\s+(.+?)\s*$",             # "Job Application for SWE Intern at Acme"
        "lever": r"^(.+?)\s+-\s+",                     # "Acme - Software Engineer Intern"
        "ashby": r"@\s*(.+?)\s*$",                     # "Software Intern @ Acme"
        "smartrecruiters": r"^(.+?)\s+[-|]\s+",
    }
    if ats not in patterns:
        return None
    m = re.search(patterns[ats], t)
    name = m.group(1).strip() if m else ""
    return name[:60] if 1 < len(name) <= 60 else None


def parse_ats_url(url: str, title: str = "") -> Optional[Company]:
    """Turn a job posting or board URL into a Company the free fetchers can read."""
    try:
        u = urlparse(url)
    except ValueError:
        return None
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]

    def make(ats: str, slug: str, **kw) -> Optional[Company]:
        if not _SLUG.match(slug):
            return None
        return Company(name=_name_from_title(ats, title) or _pretty(slug), ats=ats, slug=slug, **kw)

    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        if parts[:2] == ["embed", "job_app"] or parts[:1] == ["embed"]:
            slug = (parse_qs(u.query).get("for") or [""])[0]
            return make("greenhouse", slug) if slug else None
        return make("greenhouse", parts[0]) if parts else None
    if host == "jobs.lever.co" and parts:
        return make("lever", parts[0])
    if host == "jobs.ashbyhq.com" and parts:
        return make("ashby", parts[0])
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and parts:
        return make("smartrecruiters", parts[0])
    m = _WORKDAY_HOST.match(host)
    if m:
        rest = parts[1:] if parts and _LOCALE.match(parts[0]) else parts
        if rest and rest[0] not in ("wday", "job"):
            return make("workday", m.group(1), host=host, site=rest[0])
        return None
    if _WORKDAY_SITE_HOST.match(host) and len(parts) >= 3 and parts[0] == "recruiting":
        return make("workday", parts[1], host=host, site=parts[2])
    return None


def _validate(company: Company) -> bool:
    try:
        return len(ATS[company.ats](company)) > 0
    except Exception as exc:  # 404, renamed board, rate limit: just don't add it
        log.info("  reject %-40s %s", company.key, str(exc)[:120])
        return False


def _load_discovered(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("companies") or []


def _write_discovered(path: Path, entries: list[dict]) -> None:
    body = yaml.safe_dump({"companies": entries}, sort_keys=False, allow_unicode=True, width=200)
    path.write_text(HEADER + "\n" + body, encoding="utf-8")


def discover(queries: list[str], per_query: int, max_new: int, path: Path = DISCOVERED_FILE,
             dry_run: bool = False) -> list[Company]:
    companies, _ = load_watchlist()
    known = {c.key for c in companies}
    fc = firecrawl.client()

    candidates: dict[str, Company] = {}
    for q in queries:
        try:
            results = fc.search(q, per_query)
        except firecrawl.SourceSkipped as exc:
            log.warning("stopping searches: %s", exc)
            break
        except Exception as exc:
            log.warning("search failed %r: %s", q, str(exc)[:200])
            continue
        found = 0
        for r in results:
            c = parse_ats_url(r.get("url", ""), r.get("title", ""))
            if c and c.key not in known and c.key not in candidates:
                candidates[c.key] = c
                found += 1
        log.info("search %-60s %2d results, %2d new boards", q[:60], len(results), found)

    pool = list(candidates.values())
    with ThreadPoolExecutor(8) as ex:
        ok = [c for c, good in zip(pool, ex.map(_validate, pool)) if good]
    added = ok[:max_new]
    log.info("%d candidate boards, %d answered with postings, adding %d", len(pool), len(ok), len(added))

    if added and not dry_run:
        today = date.today().isoformat()
        entries = _load_discovered(path)
        for c in added:
            entry = {"name": c.name, "ats": c.ats, "slug": c.slug}
            if c.host:
                entry.update({"host": c.host, "site": c.site})
            entry.update({"tags": ["discovered"], "discovered": today})
            entries.append(entry)
        _write_discovered(path, entries)
    if not dry_run:
        firecrawl.save_state()
    return added


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="search and validate, but don't write discovered.yaml")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_discovery()
    try:
        added = discover(cfg.get("queries") or DEFAULT_QUERIES, int(cfg.get("results_per_query", 20)),
                         int(cfg.get("max_new_per_run", 25)), dry_run=args.dry_run)
    except firecrawl.SourceSkipped as exc:
        log.warning("discovery skipped: %s", exc)
        return 0
    for c in added:
        print(f"+ {c.key:45} {c.name}")
    usage = firecrawl.summary()
    if usage:
        print(f"Firecrawl credits this month: {usage['credits_used']}/{usage['budget']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
