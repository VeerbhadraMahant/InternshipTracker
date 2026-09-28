"""Parsers against payloads shaped like each API's documented response."""
from tracker.config import Company
from tracker.sources import ashby, greenhouse, hn, lever, remoteok, remotive, smartrecruiters, workday, wwr


def test_greenhouse():
    payload = {"jobs": [{
        "id": 123, "title": "Software Engineering Intern", "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
        "location": {"name": "Pune, India"}, "updated_at": "2026-09-01T10:00:00-04:00",
        "first_published": "2026-08-30T10:00:00-04:00",
        "content": "&lt;p&gt;Stipend &amp;amp; perks&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;",
        "offices": [{"name": "Pune", "location": "Pune, Maharashtra, India"}],
    }]}
    [j] = greenhouse.parse(payload, Company("Acme", "greenhouse", "acme", tags=["pune"]))
    assert j.title == "Software Engineering Intern"
    assert j.locations == ["Pune, India", "Pune, Maharashtra, India"]
    assert j.description == "Stipend & perks Python"
    assert j.posted_at.startswith("2026-08-30")
    assert j.tags == ["pune"]


def test_lever():
    payload = [{
        "id": "abc", "text": "ML Intern", "hostedUrl": "https://jobs.lever.co/acme/abc",
        "categories": {"location": "Remote", "allLocations": ["Remote", "Mumbai"], "commitment": "Internship"},
        "workplaceType": "remote", "createdAt": 1790000000000, "descriptionPlain": "Build models.",
        "lists": [{"text": "Requirements", "content": "<li>PyTorch</li>"}], "additionalPlain": "",
        "salaryRange": {"min": 20, "max": 30, "currency": "USD", "interval": "per-hour-wage"},
    }]
    [j] = lever.parse(payload, Company("Acme", "lever", "acme"))
    assert j.remote and j.locations == ["Remote", "Mumbai"]
    assert "Requirements: PyTorch" in j.description
    assert j.compensation == "USD 20 - 30 per hour wage"
    assert "Internship" in j.tags


def test_ashby():
    payload = {"jobs": [{
        "id": "u1", "title": "AI Engineer", "location": "Remote", "secondaryLocations": [{"location": "India"}],
        "isRemote": True, "isListed": True, "employmentType": "Intern", "publishedAt": "2026-09-01T00:00:00Z",
        "jobUrl": "https://jobs.ashbyhq.com/acme/u1", "descriptionPlain": "LLMs",
        "compensation": {"scrapeableCompensationSalarySummary": "$8K - $10K per month"},
    }, {"id": "u2", "title": "Hidden", "isListed": False}]}
    [j] = ashby.parse(payload, Company("Acme", "ashby", "acme"))
    assert j.locations == ["Remote", "India"] and j.remote
    assert j.compensation == "$8K - $10K per month"
    assert "Intern" in j.tags


def test_smartrecruiters():
    payload = {"totalFound": 1, "content": [{
        "id": "744", "name": "Software Intern", "releasedDate": "2026-09-01T00:00:00.000Z",
        "location": {"city": "Pune", "region": "MH", "country": "in", "remote": False},
        "typeOfEmployment": {"label": "Internship"}, "experienceLevel": {"label": "Internship"},
    }]}
    [j] = smartrecruiters.parse_list(payload, Company("Bosch", "smartrecruiters", "BoschGroup"))
    assert j.url == "https://jobs.smartrecruiters.com/BoschGroup/744"
    assert j.locations == ["Pune, MH, in"]
    detail = {"jobAd": {"sections": {"jobDescription": {"text": "<p>Write C++</p>"}, "qualifications": None}}}
    assert smartrecruiters.parse_detail(detail) == "Write C++"


def test_workday():
    company = Company("NVIDIA", "workday", "nvidia", site="Ext", host="nvidia.wd5.myworkdayjobs.com")
    payload = {"total": 1, "jobPostings": [{
        "title": "Deep Learning Intern", "externalPath": "/job/India-Pune/Deep-Learning-Intern_JR1",
        "locationsText": "India, Pune", "postedOn": "Posted Today",
    }]}
    [j] = workday.parse_list(payload, company)
    assert j.url == "https://nvidia.wd5.myworkdayjobs.com/Ext/job/India-Pune/Deep-Learning-Intern_JR1"
    assert j.native_id == "Deep-Learning-Intern_JR1"
    workday.apply_detail(j, {"jobPostingInfo": {
        "jobDescription": "<p>CUDA</p>", "location": "India, Pune", "additionalLocations": ["India, Mumbai"],
        "startDate": "2026-09-20", "externalUrl": "https://nvidia.wd5.myworkdayjobs.com/en-US/Ext/job/x"}})
    assert j.description == "CUDA" and j.locations == ["India, Pune", "India, Mumbai"]


def test_remoteok_skips_legal_notice():
    payload = [{"legal": "notice"}, {
        "id": "99", "position": "Frontend Intern", "company": "Acme", "location": "Worldwide",
        "description": "<b>React</b>", "date": "2026-09-01T00:00:00+00:00", "salary_min": 0, "salary_max": 0,
        "url": "https://remoteok.com/remote-jobs/99", "tags": ["react"],
    }]
    [j] = remoteok.parse(payload)
    assert j.remote and j.compensation is None and j.description == "React"


def test_remotive():
    payload = {"jobs": [{
        "id": 5, "url": "https://remotive.com/j/5", "title": "Data Intern", "company_name": "Acme",
        "job_type": "internship", "publication_date": "2026-09-01T00:00:00", "candidate_required_location": "USA",
        "salary": "", "description": "<p>SQL</p>", "tags": [],
    }]}
    [j] = remotive.parse(payload)
    assert j.locations == ["USA"] and "internship" in j.tags and j.compensation is None


def test_wwr():
    xml = """<?xml version="1.0"?><rss><channel><item>
      <title>Acme: Junior Developer Intern</title><region>Anywhere in the World</region>
      <link>https://weworkremotely.com/remote-jobs/acme-intern</link>
      <guid>https://weworkremotely.com/remote-jobs/acme-intern</guid>
      <pubDate>Mon, 01 Sep 2026 10:00:00 +0000</pubDate><description>&lt;p&gt;Go&lt;/p&gt;</description>
    </item></channel></rss>"""
    [j] = wwr.parse(xml)
    assert (j.company, j.title) == ("Acme", "Junior Developer Intern")
    assert j.locations == ["Anywhere in the World"] and j.posted_at.startswith("2026-09-01")


def test_hn():
    assert hn.latest_thread_id({"hits": [
        {"title": "Ask HN: Who wants to be hired? (September 2026)", "objectID": "1"},
        {"title": "Ask HN: Who is hiring? (September 2026)", "objectID": "2"},
    ]}) == "2"
    thread = {"children": [
        {"id": 10, "text": "Acme | Software Engineering Intern | Remote (India OK) | $2k/month<p>Details",
         "created_at": "2026-09-01T00:00:00Z"},
        {"id": 11, "text": "Other Co | Senior SRE | NYC", "created_at": "2026-09-01T00:00:00Z"},
    ]}
    [j] = hn.parse_thread(thread)
    assert j.company == "Acme" and j.title == "Software Engineering Intern" and j.remote
