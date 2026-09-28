"""Tags a role with the fields it belongs to: software, ai-ml, data."""
from __future__ import annotations

import re

from ..models import Job

RULES = {
    "ai-ml": re.compile(
        r"\b(machine learning|ml|ai|a\.i\.|artificial intelligence|deep learning|nlp|natural language|"
        r"computer vision|cv engineer|llms?|generative|genai|reinforcement learning|research scientist|"
        r"applied scientist|mlops|perception|robotics)\b", re.I),
    "data": re.compile(
        r"\b(data (science|scientist|engineer(ing)?|analyst|analytics|platform)|analytics|business intelligence|"
        r"bi developer|etl|quantitative|quant)\b", re.I),
    "software": re.compile(
        r"\b(software|swe|sde|developer|programmer|programming|back-?end|front-?end|full-?stack|web|mobile|ios|"
        r"android|devops|sre|site reliability|infrastructure|platform|cloud|security engineer|cyber ?security|"
        r"embedded|firmware|qa|test automation|sdet|systems engineer|engineering intern|"
        r"computer science|cse|it intern|technology intern|tech intern|product engineer|game dev)\b", re.I),
}

# Used only when the title is too vague (e.g. "Summer Intern 2027").
_DESC_SOFTWARE = re.compile(
    r"\b(python|java|javascript|typescript|react|node\.?js|golang|c\+\+|kotlin|swift|sql|git|"
    r"computer science|software development)\b", re.I)


def classify_fields(job: Job) -> list[str]:
    found = [name for name, rx in RULES.items() if rx.search(job.title)]
    if found:
        return found
    desc = job.description[:4000]
    found = [name for name in ("ai-ml", "data") if RULES[name].search(desc)]
    if len(_DESC_SOFTWARE.findall(desc)) >= 2:
        found.append("software")
    return found or ["other"]
