import json

from tracker import run
from tracker.config import Company, Filters
from tracker.models import Job
from tracker.store import Store


def _job(native_id, title="Software Intern", locations=("Pune, India",)):
    return Job(source="greenhouse", company="Acme", title=title, url=f"https://x/{native_id}",
               native_id=native_id, locations=list(locations))


def test_seed_then_alert_only_new_matches(tmp_path, monkeypatch):
    postings = {"acme": [_job("1"), _job("2", title="Senior Engineer")]}
    sent = []

    def fake_greenhouse(company):
        return list(postings[company.slug])

    def broken(company):
        raise RuntimeError("404")

    monkeypatch.setattr(run, "ATS", {"greenhouse": fake_greenhouse, "lever": broken})
    monkeypatch.setattr(run, "FEEDS", {})
    monkeypatch.setattr(run, "load_watchlist", lambda: (
        [Company("Acme", "greenhouse", "acme"), Company("Gone", "lever", "gone")], {}))
    monkeypatch.setattr(run, "load_filters", lambda: Filters())
    monkeypatch.setattr(run, "Store", lambda: Store(tmp_path))
    monkeypatch.setattr(run.alerts, "send_all", lambda jobs, url: sent.append(jobs) or {})

    assert run.main([]) == 0          # first run seeds silently
    assert sent == []
    data = json.loads((tmp_path / "jobs.json").read_text())
    assert [j["title"] for j in data["jobs"]] == ["Software Intern"]   # non-internships not stored
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["scopes"]["lever:gone"]["ok"] is False
    assert status["scopes"]["greenhouse:acme"]["internships"] == 1

    postings["acme"] += [_job("3", title="ML Intern", locations=["Remote - India"]),
                         _job("4", title="Data Intern", locations=["Remote - US"])]
    assert run.main([]) == 0
    assert len(sent) == 1 and [j.title for j in sent[0]] == ["ML Intern"]


def test_all_sources_failing_exits_nonzero(tmp_path, monkeypatch):
    def broken(company):
        raise RuntimeError("down")

    monkeypatch.setattr(run, "ATS", {"greenhouse": broken})
    monkeypatch.setattr(run, "FEEDS", {})
    monkeypatch.setattr(run, "load_watchlist", lambda: ([Company("Acme", "greenhouse", "acme")], {}))
    monkeypatch.setattr(run, "load_filters", lambda: Filters())
    monkeypatch.setattr(run, "Store", lambda: Store(tmp_path))
    assert run.main([]) == 1


def test_dedupe_prefers_company_ats():
    feed = Job(source="remoteok", company="Acme", title="ML Intern", url="a", native_id="f")
    ats = Job(source="greenhouse", company="acme ", title="ml intern", url="b", native_id="g")
    assert [j.source for j in run._dedupe([feed, ats])] == ["greenhouse"]
    assert [j.source for j in run._dedupe([ats, feed])] == ["greenhouse"]
