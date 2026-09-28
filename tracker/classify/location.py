"""Buckets locations into pune / mumbai / india / remote / other."""
from __future__ import annotations

import re

from ..models import Job

PUNE = re.compile(r"\b(pune|poona|hinjewadi|hinjawadi|kharadi|magarpatta|hadapsar|baner|viman nagar|"
                  r"yerwada|pimpri|chinchwad|kalyani nagar|wakad|balewadi)\b", re.I)
MUMBAI = re.compile(r"\b(mumbai|bombay|navi mumbai|thane|powai|andheri|bkc|bandra kurla|lower parel|"
                    r"goregaon|malad|vikhroli|airoli|belapur|vashi|worli)\b", re.I)
INDIA = re.compile(r"\b(india|bengaluru|bangalore|hyderabad|chennai|gurgaon|gurugram|noida|delhi|"
                   r"new delhi|kolkata|ahmedabad|jaipur|kochi|trivandrum|coimbatore|indore|chandigarh|"
                   r"maharashtra|karnataka|telangana|tamil nadu)\b", re.I)
REMOTE = re.compile(r"\b(remote|anywhere|work from home|wfh|distributed|worldwide|global)\b", re.I)


def classify_location(job: Job) -> list[str]:
    loc_text = " / ".join(job.locations)
    tags: list[str] = []
    if PUNE.search(loc_text):
        tags.append("pune")
    if MUMBAI.search(loc_text):
        tags.append("mumbai")
    if tags or INDIA.search(loc_text):
        tags.append("india")
    if job.remote or REMOTE.search(loc_text) or re.search(r"\bremote\b", job.title, re.I):
        tags.append("remote")
    return tags or ["other"]
