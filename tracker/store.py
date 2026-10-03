"""Git-as-database: data/jobs.json holds current roles, data/seen.json every id ever seen."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import DATA_DIR
from .models import Job

MISSES_BEFORE_CLOSED = 2       # consecutive successful fetches without the job
KEEP_CLOSED_DAYS = 7           # then drop it from jobs.json (seen.json still remembers the id)
DESCRIPTION_CHARS = 1200       # description shipped to the dashboard


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    tmp.replace(path)


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.jobs: dict[str, Job] = {
            d["id"]: Job.from_dict(d) for d in _read(data_dir / "jobs.json", {}).get("jobs", [])
        }
        self.seen: dict[str, str] = _read(data_dir / "seen.json", {})
        self.status: dict = _read(data_dir / "status.json", {})

    @property
    def is_empty(self) -> bool:
        return not self.seen

    def merge(self, fetched: list[Job], ok_scopes: set[str], ts: str | None = None) -> list[Job]:
        """Merge one run's results. Returns jobs never seen before.

        Only scopes that fetched successfully can close jobs; a source that errored
        or was skipped leaves its jobs untouched.
        """
        ts = ts or now_iso()
        new: list[Job] = []
        fetched_ids = set()
        for job in fetched:
            fetched_ids.add(job.id)
            job.description = job.description[:DESCRIPTION_CHARS]
            job.last_seen, job.status, job.missed_runs = ts, "open", 0
            if job.id in self.seen:
                job.first_seen = self.seen[job.id]
            else:
                job.first_seen = ts
                self.seen[job.id] = ts
                new.append(job)
            self.jobs[job.id] = job

        cutoff = (datetime.fromisoformat(ts) - timedelta(days=KEEP_CLOSED_DAYS)).isoformat()
        for job_id, job in list(self.jobs.items()):
            if job_id in fetched_ids or job.scope not in ok_scopes:
                continue
            job.missed_runs += 1
            if job.missed_runs >= MISSES_BEFORE_CLOSED:
                job.status = "closed"
            if job.status == "closed" and (job.last_seen or "") < cutoff:
                del self.jobs[job_id]
        return new

    def retire(self, active_scopes: set[str], ts: str | None = None) -> int:
        """Close jobs from sources that were removed from the config, and forget their status.

        Without this, a dropped source's jobs would never be seen as missing (the source is no
        longer fetched) and would stay open on the dashboard forever.
        """
        ts = ts or now_iso()
        cutoff = (datetime.fromisoformat(ts) - timedelta(days=KEEP_CLOSED_DAYS)).isoformat()
        closed = 0
        for job_id, job in list(self.jobs.items()):
            if not job.scope or job.scope in active_scopes:
                continue
            if job.status == "open":
                job.status, job.last_seen = "closed", ts
                closed += 1
            elif (job.last_seen or "") < cutoff:
                del self.jobs[job_id]
        scopes = self.status.get("scopes", {})
        for scope in [s for s in scopes if s not in active_scopes]:
            del scopes[scope]
        return closed

    def save(self, ts: str | None = None) -> None:
        jobs = sorted(self.jobs.values(), key=lambda j: (j.first_seen or "", j.id), reverse=True)
        _write(self.data_dir / "jobs.json", {"generated_at": ts or now_iso(), "jobs": [j.to_dict() for j in jobs]})
        _write(self.data_dir / "seen.json", dict(sorted(self.seen.items())))
        _write(self.data_dir / "status.json", self.status)
