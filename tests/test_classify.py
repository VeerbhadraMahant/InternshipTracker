import pytest

from tracker.classify import classify
from tracker.classify.field import classify_fields
from tracker.classify.internship import is_internship
from tracker.classify.location import classify_location
from tracker.classify.stipend import extract_stipend
from tracker.models import Job


def job(title="Software Engineering Intern", locations=(), remote=False, description="", compensation=None, tags=()):
    return Job(source="test", company="Acme", title=title, url="https://x", native_id=title,
               locations=list(locations), remote=remote, description=description,
               compensation=compensation, tags=list(tags))


@pytest.mark.parametrize("title,expected", [
    ("Software Engineering Intern", True),
    ("Summer 2027 Internship - Machine Learning", True),
    ("Graduate Engineer Trainee", True),
    ("SDE Co-op (Fall)", True),
    ("Senior Software Engineer", False),
    ("Internship Program Manager", False),
    ("University Recruiter, Interns", False),
    ("Internal Tools Engineer", False),
    ("International Sales Associate", False),
])
def test_internship_title(title, expected):
    assert is_internship(job(title)) is expected


def test_internship_from_structured_tag():
    assert is_internship(job("Software Engineer", tags=["Intern"]))


@pytest.mark.parametrize("title,expected", [
    ("Machine Learning Intern", ["ai-ml"]),
    ("AI Research Intern", ["ai-ml"]),
    ("Data Analyst Intern", ["data"]),
    ("Backend Developer Intern", ["software"]),
    ("Marketing Intern", ["other"]),
])
def test_fields_from_title(title, expected):
    assert classify_fields(job(title)) == expected


def test_fields_description_needs_specific_ai_terms():
    j = job("HR Apprentice", description="Join our AI-driven bank's people team. ML experience not needed.")
    assert classify_fields(j) == ["other"]
    j = job("Summer Intern", description="Train models in PyTorch and evaluate LLMs.")
    assert "ai-ml" in classify_fields(j)


def test_fields_fallback_to_description():
    j = job("Summer Intern 2027", description="You will write Python and SQL services with React frontends.")
    assert classify_fields(j) == ["software"]


@pytest.mark.parametrize("locations,remote,expected", [
    (["Pune, Maharashtra, India"], False, ["pune", "india"]),
    (["Hinjewadi Phase 2"], False, ["pune", "india"]),
    (["Navi Mumbai"], False, ["mumbai", "india"]),
    (["Bengaluru, India"], False, ["india"]),
    (["Remote - India"], False, ["india", "remote"]),
    (["San Francisco, CA"], True, ["remote"]),
    (["London, UK"], False, ["other"]),
])
def test_location(locations, remote, expected):
    assert classify_location(job(locations=locations, remote=remote)) == expected


@pytest.mark.parametrize("locations,description,label,detail_contains", [
    (["Pune, India"], "", "india-ok", "Pune"),
    (["New York, NY"], "", "onsite-abroad", "New York"),
    (["Remote - US"], "", "restricted", "US"),
    (["Remote (APAC)"], "", "india-ok", "APAC"),
    (["Remote"], "Candidates must be located in the United States.", "restricted", "United States"),
    (["Remote"], "This role is open only to candidates based in Canada.", "restricted", "Canada"),
    (["Remote"], "US-only position.", "restricted", "US"),
    (["Worldwide"], "You must be authorized to work in the US. We cannot sponsor visas.", "needs-work-auth", "US"),
    (["Remote"], "We are unable to sponsor visas for this role.", "needs-work-auth", ""),
    (["Remote"], "You'll work UTC-5 to UTC+1 core hours.", "timezone", "UTC-5"),
    (["Remote"], "Core hours overlap: UTC+3 to UTC+9.", "unknown", ""),
    (["Remote"], "You need 4 hours of overlap with PST business hours.", "timezone", "PST"),
    (["Remote"], "Must be able to work in IST hours.", "india-ok", "IST"),
    (["Worldwide"], "We are a fully distributed team.", "open-worldwide", "Worldwide"),
    (["Remote"], "Work from anywhere in the world.", "open-worldwide", "Worldwide"),
    (["Remote"], "Join our team building developer tools.", "unknown", ""),
    (["Remote"], "Applicants must be located in India.", "india-ok", "India"),
    (["Remote"], "We work async and use GMT time for meeting invites.", "unknown", ""),
    (["Remote"], "Help us reach users in the US and Europe.", "unknown", ""),
    (["Remote"], "We are a global company building self-driving cars.", "unknown", ""),
    (["Remote"], "Our global team works globally across time zones.", "unknown", ""),
    (["San Francisco, CA; Remote"], "", "restricted", "US"),
    (["Remote"], "We hire globally; this role is fully remote.", "open-worldwide", "Worldwide"),
    (["Anywhere"], "Must be a US citizen.", "needs-work-auth", ""),
])
def test_eligibility(locations, description, label, detail_contains):
    j = classify(job(locations=locations, description=description))
    assert j.eligibility == label, (j.eligibility, j.eligibility_detail, j.eligibility_evidence)
    assert detail_contains in j.eligibility_detail


def test_eligibility_evidence_is_the_matched_phrase():
    j = classify(job(locations=["Remote"], description="Great team. Candidates must be located in the United States. Apply!"))
    assert "must be located in the United States" in j.eligibility_evidence


@pytest.mark.parametrize("description,compensation,inr,text_contains", [
    ("Stipend: ₹25,000 per month", None, 25000, "25,000"),
    ("Stipend of Rs. 30000/month for 6 months", None, 30000, "30000"),
    ("Pay: $20/hr", None, 20 * 88 * 160, "$20"),
    ("", "USD 40 - 50 per hour", 40 * 88 * 160, "40"),
    ("Salary: 6 LPA on conversion", None, 50000, "LPA"),
    ("We raised $20M in Series B funding.", None, None, ""),
    ("A $10k signing bonus for engineers.", None, None, ""),
    ("This is an unpaid internship.", None, 0, "Unpaid"),
    ("Monthly stipend €1,500", None, 1500 * 103, "1,500"),
    ("", None, None, ""),
])
def test_stipend(description, compensation, inr, text_contains):
    s = extract_stipend(job(description=description, compensation=compensation))
    assert s.inr_month == inr, s
    assert text_contains in s.text
