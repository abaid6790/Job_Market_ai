"""
Job posting section detection — thin wrapper around the shared header
scanner (app.services.nlp.section_scanner) with job-posting-specific
header synonyms.
"""
from app.services.nlp.section_scanner import scan_sections

SECTION_SYNONYMS = {
    "about": ["about us", "about the company", "about the role", "company overview", "who we are", "overview"],
    "responsibilities": [
        "responsibilities", "key responsibilities", "what you'll do", "duties",
        "role responsibilities", "the role", "what you will do",
    ],
    "requirements": [
        "requirements", "required qualifications", "must have", "minimum qualifications",
        "basic qualifications", "required skills", "qualifications", "what you'll need",
        "what you need",
    ],
    "preferred": [
        "preferred qualifications", "nice to have", "preferred skills", "bonus points",
        "good to have", "desired skills", "nice-to-haves", "preferred", "bonus skills",
    ],
    "benefits": ["benefits", "perks", "what we offer", "compensation and benefits", "why join us"],
    "compensation": ["compensation", "salary", "pay range", "compensation range"],
}


def detect_sections(text: str) -> dict:
    return scan_sections(text, SECTION_SYNONYMS)
