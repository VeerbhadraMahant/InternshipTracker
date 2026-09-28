from tracker import alerts
from tracker.classify import classify
from tracker.config import Filters
from tracker.models import Job
from tracker.store import Store


def mk(native_id, scope="greenhouse:acme", **kw):
    defaults = dict(source="greenhouse", company="Acme", title="Software Intern", url="https://x",
                    native_id=native_id, locations=["Pune, India"])
    defaults.update(kw)
    j = Job(**defaults)
    j.scope = scope
    return classify(j)


def test_merge_detects_new_and_keeps_first_seen(tmp_path):
    s = Store(tmp_path)
    assert s.is_empty
    new = s.merge([mk("1"), mk("2")], {"greenhouse:acme"}, "2026-09-01T00:00:00+00:00")
    assert {j.native_id for j in new} == {"1", "2"}
    s.save("2026-09-01T00:00:00+00:00")

    s = Store(tmp_path)
    new = s.merge([mk("1"), mk("3")], {"greenhouse:acme"}, "2026-09-01T02:00:00+00:00")
    assert [j.native_id for j in new] == ["3"]
    job1 = next(j for j in s.jobs.values() if j.native_id == "1")
    assert job1.first_seen == "2026-09-01T00:00:00+00:00"


def test_closing_needs_two_successful_misses(tmp_path):
    s = Store(tmp_path)
    s.merge([mk("1")], {"greenhouse:acme"}, "2026-09-01T00:00:00+00:00")
    job_id = next(iter(s.jobs))
    s.merge([], set(), "2026-09-01T02:00:00+00:00")  # source failed: untouched
    assert s.jobs[job_id].status == "open" and s.jobs[job_id].missed_runs == 0
    s.merge([], {"greenhouse:acme"}, "2026-09-01T04:00:00+00:00")
    assert s.jobs[job_id].status == "open"
    s.merge([], {"greenhouse:acme"}, "2026-09-01T06:00:00+00:00")
    assert s.jobs[job_id].status == "closed"
    s.merge([], {"greenhouse:acme"}, "2026-09-20T00:00:00+00:00")  # closed > 7 days: dropped
    assert job_id not in s.jobs and job_id in s.seen


def test_matches_filters():
    f = Filters()
    assert alerts.matches(mk("1"), f)
    assert not alerts.matches(mk("2", locations=["Bengaluru"]), f)          # india, not pune/mumbai/remote
    assert not alerts.matches(mk("3", locations=["Remote - US"]), f)        # restricted
    assert not alerts.matches(mk("4", title="Marketing Intern"), f)          # field
    assert alerts.matches(mk("5", locations=["Remote"]), f)                  # unknown eligibility allowed
    paid = mk("6", description="Stipend ₹10,000 per month")
    assert alerts.matches(paid, f)
    assert not alerts.matches(paid, Filters(min_stipend_inr_month=20000))
    assert not alerts.matches(mk("7"), Filters(include_undisclosed_stipend=False))


def test_email_render_escapes_html():
    j = mk("1", title="<script>Intern</script>")
    text, body = alerts.email.render([j], "https://dash")
    assert "<script>" not in body and "&lt;script&gt;" in body
    assert "https://dash" in text
