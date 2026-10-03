"""Entry point: python -m tracker.run [--dry-run] [--seed] [--test-alert] [--only SCOPE]"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Callable

from . import alerts, firecrawl
from .classify import classify
from .config import Company, load_filters, load_watchlist
from .models import Job
from .sources import ATS, FEEDS
from .store import Store, now_iso

log = logging.getLogger("tracker")
MAX_WORKERS = 8


def _task_list(companies: list[Company], feeds: dict, store: Store, only: str | None):
    """Yield (scope, callable) pairs for everything due this run."""
    tasks: list[tuple[str, Callable[[], list[Job]]]] = []
    for c in companies:
        fetcher = ATS.get(c.ats)
        if not fetcher:
            log.warning("unknown ats %r for %s", c.ats, c.name)
            continue
        tasks.append((c.key, lambda c=c, f=fetcher: f(c)))
    now = datetime.now(timezone.utc)
    for name, cfg in feeds.items():
        cfg = cfg or {}
        if name not in FEEDS or cfg.get("enabled", True) is False:
            continue
        last_ok = (store.status.get("scopes", {}).get(name) or {}).get("last_ok")
        min_h = cfg.get("min_interval_hours", 0)
        if not only and last_ok and min_h and now - datetime.fromisoformat(last_ok) < timedelta(hours=min_h):
            log.info("skip %s (polled %s, min interval %sh)", name, last_ok, min_h)
            continue
        tasks.append((name, lambda cfg=cfg, f=FEEDS[name]: f(cfg)))
    if only:
        tasks = [t for t in tasks if t[0] == only or t[0].startswith(only + ":")]
    return tasks


def fetch_all(tasks) -> tuple[list[Job], dict[str, dict]]:
    jobs: list[Job] = []
    report: dict[str, dict] = {}
    with ThreadPoolExecutor(MAX_WORKERS) as pool:
        futures = {pool.submit(fn): scope for scope, fn in tasks}
        for fut in as_completed(futures):
            scope = futures[fut]
            try:
                batch = fut.result()
            except firecrawl.SourceSkipped as exc:
                log.info("skip %-32s %s", scope, exc)
                report[scope] = {"ok": False, "skipped": str(exc)[:200]}
                continue
            except Exception as exc:
                log.warning("FAIL %-32s %s", scope, str(exc)[:200])
                report[scope] = {"ok": False, "error": str(exc)[:300]}
                continue
            for job in batch:
                job.scope = scope
                classify(job)
            interns = [j for j in batch if j.is_internship]
            jobs.extend(interns)
            report[scope] = {"ok": True, "fetched": len(batch), "internships": len(interns)}
            log.info("ok   %-32s %4d postings, %3d internships", scope, len(batch), len(interns))
    return jobs, report


def _dedupe(jobs: list[Job]) -> list[Job]:
    """Collapse the same role appearing on several feeds (same company + title)."""
    out: dict[tuple[str, str], Job] = {}
    for j in jobs:
        key = (j.company.lower().strip(), j.title.lower().strip())
        if key not in out or out[key].source in FEEDS and j.source not in FEEDS:  # prefer the company's own ATS
            out[key] = j
    return list(out.values())


def update_status(store: Store, report: dict[str, dict], ts: str) -> None:
    scopes = store.status.setdefault("scopes", {})
    for scope, r in report.items():
        entry = scopes.setdefault(scope, {})
        if "skipped" in r:
            # Did no work on purpose (unchanged page, no key, budget). Not a failure.
            entry.update({"last_run": ts, "skipped": r["skipped"], "error": None})
            entry.setdefault("ok", True)
            continue
        entry.pop("skipped", None)
        entry.update({"last_run": ts, "ok": r["ok"]})
        if r["ok"]:
            entry.update({"last_ok": ts, "fetched": r["fetched"], "internships": r["internships"], "error": None})
            entry["consecutive_failures"] = 0
        else:
            entry["error"] = r["error"]
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
    store.status["last_run"] = ts
    store.status["sources_ok"] = sum(1 for r in report.values() if r["ok"])
    store.status["sources_failed"] = sum(1 for r in report.values() if not r["ok"] and "skipped" not in r)
    store.status["sources_skipped"] = sum(1 for r in report.values() if "skipped" in r)
    usage = firecrawl.summary()
    if usage:
        store.status["firecrawl"] = usage


def _sample_job() -> Job:
    job = Job(source="greenhouse", company="Example Labs", title="Machine Learning Intern (Remote, India)",
              url="https://example.com/jobs/1", native_id="sample", locations=["Remote - India"], remote=True,
              description="Paid internship. Stipend: ₹40,000 per month. Open to students in India.")
    job.first_seen = now_iso()
    return classify(job)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="fetch and classify, no writes, no alerts")
    ap.add_argument("--seed", action="store_true", help="record everything as seen without alerting")
    ap.add_argument("--test-alert", action="store_true", help="send one sample alert and exit")
    ap.add_argument("--only", help="run a single scope, e.g. greenhouse:stripe or remoteok")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    dashboard = os.environ.get("DASHBOARD_URL", "")

    if args.test_alert:
        print(alerts.send_all([_sample_job()], dashboard))
        return 0

    companies, feeds = load_watchlist()
    filters = load_filters()
    store = Store()
    ts = now_iso()

    tasks = _task_list(companies, feeds, store, args.only)
    log.info("polling %d sources", len(tasks))
    jobs, report = fetch_all(tasks)
    jobs = _dedupe(jobs)
    ok_scopes = {s for s, r in report.items() if r["ok"]}

    if args.dry_run:
        for j in sorted(jobs, key=lambda j: j.company)[:60]:
            print(f"{j.company[:24]:24} | {j.title[:48]:48} | {','.join(j.location_tags):18} | "
                  f"{j.eligibility:15} | {j.stipend_inr_month}")
        print(f"\n{len(jobs)} internships from {len(ok_scopes)}/{len(report)} sources")
        return 0

    seeding = args.seed or store.is_empty
    new = store.merge(jobs, ok_scopes, ts)
    update_status(store, report, ts)
    to_alert = [] if seeding else [j for j in new if alerts.matches(j, filters)]
    store.status["last_new"] = len(new)
    store.status["last_alerted"] = len(to_alert)
    store.save(ts)
    firecrawl.save_state()

    log.info("%d new (%d match filters)%s", len(new), len(to_alert), " — seeding, no alerts" if seeding else "")
    if to_alert:
        log.info("alerts: %s", alerts.send_all(to_alert, dashboard))
    # Fail the workflow only if every source failed (network outage, broken config).
    failed = [s for s, r in report.items() if not r["ok"] and "skipped" not in r]
    return 1 if failed and not ok_scopes else 0


if __name__ == "__main__":
    sys.exit(main())
