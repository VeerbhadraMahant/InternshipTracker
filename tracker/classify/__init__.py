from ..models import Job
from .eligibility import classify_eligibility
from .field import classify_fields
from .internship import is_internship
from .location import classify_location
from .stipend import extract_stipend


def classify(job: Job) -> Job:
    job.is_internship = is_internship(job)
    job.fields = classify_fields(job)
    job.location_tags = classify_location(job)
    verdict = classify_eligibility(job, job.location_tags)
    job.eligibility, job.eligibility_detail, job.eligibility_evidence = verdict.label, verdict.detail, verdict.evidence[:300]
    stipend = extract_stipend(job)
    job.stipend_inr_month, job.stipend_text = stipend.inr_month, stipend.text
    return job
