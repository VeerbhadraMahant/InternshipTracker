import pytest
import yaml

from tracker import discover, firecrawl
from tracker.config import Company, load_watchlist
from tracker.models import Job
from tracker.sources import careerpage


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, **kw):
        self.calls.append((url, json))
        return FakeResponse(self.responses.pop(0))


@pytest.fixture
def fc(tmp_path, monkeypatch):
    """A client with an empty state file and a fake HTTP session the test fills in."""
    fake = FakeSession([])
    monkeypatch.setattr(firecrawl, "session", lambda: fake)
    client = firecrawl.Firecrawl("fc-test", firecrawl.FirecrawlState(tmp_path / "fc.json"), budget=20)
    monkeypatch.setattr(firecrawl, "client", lambda: client)
    client.fake = fake
    return client


# ---------- budget ----------

def test_budget_counts_actual_credits_and_refuses_past_limit(fc):
    fc.fake.responses = [{"success": True, "data": {"web": []}, "creditsUsed": 4}]
    fc.search("x", limit=20)
    assert fc.state.credits_used == 4
    fc.state.credits_used = 19
    with pytest.raises(firecrawl.BudgetExceeded):
        fc.scrape("https://example.com", json_schema={"type": "object"})  # needs 5
    assert fc.state.credits_used == 19 and fc.fake.calls[-1][0].endswith("/search")


def test_failed_call_is_not_counted(fc, monkeypatch):
    class Boom:
        def post(self, *a, **k):
            raise RuntimeError("down")
    monkeypatch.setattr(firecrawl, "session", lambda: Boom())
    with pytest.raises(RuntimeError):
        fc.scrape("https://example.com")
    assert fc.state.credits_used == 0


def test_state_resets_each_month(tmp_path):
    path = tmp_path / "fc.json"
    path.write_text('{"month": "2020-01", "credits_used": 800, "pages": {"u": {"hash": "h"}}}')
    state = firecrawl.FirecrawlState(path)
    assert state.credits_used == 0 and state.page_hash("u") == "h"


def test_client_without_key_skips(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setattr(firecrawl, "_client", None)
    with pytest.raises(firecrawl.SourceSkipped):
        firecrawl.client()


# ---------- career pages ----------

PAGE = Company(name="Acme", ats="careerpage", url="https://acme.in/careers", location="Pune, India", tags=["pune"])
MARKDOWN = """# Careers at Acme
Posted 3 days ago
- [Software Engineering Intern](https://acme.in/careers/123) - Pune
- [Senior Backend Engineer](https://acme.in/careers/124)
- [Data Science Trainee](/careers/125)
- [Internship FAQ](#faq)
"""


def test_extract_links_keeps_internships_and_resolves_relative_urls():
    jobs = careerpage.extract_links(MARKDOWN, PAGE)
    assert [(j.title, j.url) for j in jobs] == [
        ("Software Engineering Intern", "https://acme.in/careers/123"),
        ("Data Science Trainee", "https://acme.in/careers/125"),
    ]
    assert jobs[0].locations == ["Pune"] and jobs[0].tags == ["pune"]          # read from "- Pune"
    assert jobs[1].locations == ["Pune, India"]                                # entry default


# Trimmed from a real Firecrawl scrape of Google's internship search (Oct 2026).
GOOGLE_MD = r"""## Jobs search results

2 jobs matched

- ### Software Engineering PhD Intern, Summer 2027

_corporate\_fare_ Google_place_ Bengaluru, Karnataka, India; Hyderabad, Telangana, India; +2 more_bar\_chart_ Intern & Apprentice

Google \| Bengaluru, Karnataka, India; Hyderabad, Telangana, India; +2 more

#### Minimum qualifications

  - Pursuing a PhD program with a focus in software development.

Learn more [Learn more about Software Engineering PhD Intern, Summer 2027](https://www.google.com/about/careers/applications/jobs/results/109976286780105414-software-engineering-phd-intern-summer-2027?q=intern)

_share_
Share Software Engineering PhD Intern, Summer 2027

- ### Silicon Engineering Intern, PhD, Summer 2027

Google \| Bengaluru, Karnataka, India; Hyderabad, Telangana, India

Learn more [Learn more about Silicon Engineering Intern, PhD, Summer 2027](https://www.google.com/about/careers/applications/jobs/results/109375266236572358-silicon-engineering-intern-phd-summer-2027?q=intern)
"""

# Trimmed from a real Firecrawl scrape of metacareers.com internships (Oct 2026).
META_MD = r"""Search by technology, team, location, or ref. code

[**DFX Engineering Intern**\\
\\
Sunnyvale, CA⋅Seattle, WA\\
\\
AR/VR\\
\\
Hardware](https://www.metacareers.com/profile/job_details/1095054769939445) [**Production Engineer Intern**\\
\\
London, UK\\
\\
Infrastructure](https://www.metacareers.com/profile/job_details/1442284501111979)

Page 1 of 1"""

BIG = Company(name="Google", ats="careerpage", url="https://www.google.com/about/careers/applications/", location="India")


def test_extract_links_google_markup():
    jobs = careerpage.extract_links(GOOGLE_MD, BIG)
    assert [j.title for j in jobs] == ["Software Engineering PhD Intern, Summer 2027",
                                       "Silicon Engineering Intern, PhD, Summer 2027"]
    assert jobs[0].locations == ["Bengaluru, Karnataka, India; Hyderabad, Telangana, India; +2 more"]
    assert jobs[1].locations == ["Bengaluru, Karnataka, India; Hyderabad, Telangana, India"]


def test_extract_links_meta_multiline_links():
    jobs = careerpage.extract_links(META_MD, Company(name="Meta", ats="careerpage", url="https://www.metacareers.com/"))
    assert [(j.title, j.locations) for j in jobs] == [
        ("DFX Engineering Intern", ["Sunnyvale, CA⋅Seattle, WA"]),
        ("Production Engineer Intern", ["London, UK"]),
    ]


def test_careerpage_skips_unchanged_page_and_ignores_relative_dates(fc):
    fc.fake.responses = [{"success": True, "data": {"markdown": MARKDOWN}}]
    assert len(careerpage.fetch(PAGE)) == 2
    fc.fake.responses = [{"success": True, "data": {"markdown": MARKDOWN.replace("3 days", "4 days")}}]
    with pytest.raises(firecrawl.SourceSkipped, match="unchanged"):
        careerpage.fetch(PAGE)
    assert fc.state.credits_used == 2


def test_careerpage_falls_back_to_json_extraction(fc):
    plain = "We hire interns every summer. Apply through our portal."
    fc.fake.responses = [
        {"success": True, "data": {"markdown": plain}},
        {"success": True, "data": {"json": {"jobs": [{"title": "ML Intern", "location": "Mumbai", "url": "/j/9"}]}}},
    ]
    [job] = careerpage.fetch(PAGE)
    assert (job.title, job.url, job.locations) == ("ML Intern", "https://acme.in/j/9", ["Mumbai"])
    assert fc.state.credits_used == 6  # 1 markdown + 5 json


# ---------- discovery ----------

@pytest.mark.parametrize("url,title,expected", [
    ("https://job-boards.greenhouse.io/acme/jobs/123", "Job Application for SWE Intern at Acme Labs",
     ("greenhouse", "acme", "Acme Labs")),
    ("https://boards.greenhouse.io/embed/job_app?for=zeta&token=1", "", ("greenhouse", "zeta", "Zeta")),
    ("https://jobs.lever.co/aleph/4f1c", "Finance Intern - Aleph - Lever", ("lever", "aleph", "Aleph")),
    ("https://jobs.lever.co/fampay/1", "Copy Intern - FamPay", ("lever", "fampay", "FamPay")),
    ("https://jobs.lever.co/mactores", "Mactores - Lever", ("lever", "mactores", "Mactores")),
    ("https://jobs.lever.co/hrs/9", "QA - Lever", ("lever", "hrs", "Hrs")),
    ("https://job-boards.greenhouse.io/rubrik/jobs/1", "Careers at Rubrik | Discover The Power of You",
     ("greenhouse", "rubrik", "Rubrik")),
    ("https://job-boards.greenhouse.io/hubspotjobs/jobs/1", "Open Positions - HubSpot", ("greenhouse", "hubspotjobs", "Hubspotjobs")),
    ("https://jobs.ashbyhq.com/sarvam/abc", "AI Intern @ Sarvam AI", ("ashby", "sarvam", "Sarvam AI")),
    ("https://jobs.smartrecruiters.com/BoschGroup/7441", "", ("smartrecruiters", "BoschGroup", "Boschgroup")),
    ("https://citi.wd5.myworkdayjobs.com/en-US/2/job/Pune-India/Intern_123", "", ("workday", "citi", "Citi")),
    ("https://wd3.myworkdaysite.com/recruiting/ubs/UBS_Careers/job/x", "", ("workday", "ubs", "Ubs")),
    ("https://jobs.eu.lever.co/acme/1", "", None),
    ("https://www.linkedin.com/jobs/view/1", "", None),
])
def test_parse_ats_url(url, title, expected):
    c = discover.parse_ats_url(url, title)
    assert (c and (c.ats, c.slug, c.name)) == expected or (c is None and expected is None)


def test_parse_workday_keeps_host_and_site():
    c = discover.parse_ats_url("https://citi.wd5.myworkdayjobs.com/en-US/2/job/Pune/Intern_1")
    assert (c.host, c.site, c.key) == ("citi.wd5.myworkdayjobs.com", "2", "workday:citi")


def test_discover_adds_only_new_validated_boards(fc, tmp_path, monkeypatch):
    out = tmp_path / "discovered.yaml"
    monkeypatch.setattr(discover, "load_watchlist", lambda: load_watchlist(discovered=tmp_path / "none.yaml"))
    fc.fake.responses = [{"success": True, "creditsUsed": 4, "data": {"web": [
        {"url": "https://jobs.lever.co/meesho/1", "title": "Meesho - Intern"},
        {"url": "https://jobs.lever.co/cred/2", "title": "CRED - Intern"},       # already in watchlist.yaml
        {"url": "https://jobs.lever.co/deadboard/3", "title": "Dead - Intern"},  # validation fails
    ]}}]
    def fake_lever(c):
        if c.slug == "deadboard":
            raise RuntimeError("404")
        return [Job(source="lever", company=c.name, title="Intern", url="u", native_id="1", locations=["Bengaluru"])]
    monkeypatch.setitem(discover.ATS, "lever", fake_lever)
    added = discover.discover(["q"], 20, 25, path=out)
    assert [c.key for c in added] == ["lever:meesho"]
    saved = yaml.safe_load(out.read_text())["companies"]
    assert saved[0]["slug"] == "meesho" and saved[0]["tags"] == ["discovered"]


def test_load_watchlist_merges_discovered_without_duplicates(tmp_path):
    wl = tmp_path / "w.yaml"
    wl.write_text("companies:\n  - {name: Acme, ats: lever, slug: acme}\nfeeds: {}\n")
    disc = tmp_path / "d.yaml"
    disc.write_text("companies:\n  - {name: Acme again, ats: lever, slug: acme}\n"
                    "  - {name: New, ats: ashby, slug: new, discovered: '2026-10-05'}\n")
    companies, _ = load_watchlist(wl, disc)
    assert [c.key for c in companies] == ["lever:acme", "ashby:new"]


def test_discover_validates_candidates_without_firecrawl(tmp_path, monkeypatch):
    out = tmp_path / "discovered.yaml"
    monkeypatch.setattr(discover, "load_watchlist", lambda: load_watchlist(discovered=tmp_path / "none.yaml"))
    monkeypatch.setattr(discover.firecrawl, "client",
                        lambda: (_ for _ in ()).throw(firecrawl.SourceSkipped("no key")))
    def fake_gh(c):
        loc = {"pubmatic": "Pune, India", "usonly": "Remote - US"}.get(c.slug)
        return [Job(source="greenhouse", company=c.name, title="Intern", url="u", native_id="1", locations=[loc])] if loc else []
    monkeypatch.setitem(discover.ATS, "greenhouse", fake_gh)
    seeds = [
        {"name": "PubMatic", "ats": "greenhouse", "slug": "pubmatic", "tags": ["pune"]},
        {"name": "Guess", "ats": "greenhouse", "slug": "wrongslug"},       # answers with nothing
        {"name": "US only", "ats": "greenhouse", "slug": "usonly"},        # remote, but US only
        {"name": "Druva", "ats": "greenhouse", "slug": "druva"},            # already in watchlist.yaml
    ]
    added = discover.discover(["q"], 20, 25, path=out, seeds=seeds)
    assert [c.key for c in added] == ["greenhouse:pubmatic"]
    assert yaml.safe_load(out.read_text())["companies"][0]["tags"] == ["pune"]


def test_recheck_drops_boards_without_india_roles(tmp_path, monkeypatch):
    path = tmp_path / "discovered.yaml"
    discover._write_discovered(path, [
        {"name": "Keep", "ats": "greenhouse", "slug": "keep"},
        {"name": "US only", "ats": "greenhouse", "slug": "usonly"},
    ])
    monkeypatch.setitem(discover.ATS, "greenhouse", lambda c: [Job(
        source="greenhouse", company=c.name, title="Intern", url="u", native_id="1",
        locations=["Pune, India" if c.slug == "keep" else "Austin, TX"])])
    assert discover.recheck(path) == ["US only"]
    assert [e["slug"] for e in yaml.safe_load(path.read_text())["companies"]] == ["keep"]
