"""
Resume section detection — thin wrapper around the shared header scanner
(app.services.nlp.section_scanner) with resume-specific header synonyms.
"""
from app.services.nlp.section_scanner import scan_sections

SECTION_SYNONYMS = {
    "summary": ["summary", "professional summary", "profile", "objective", "about me", "career objective"],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment history", "work history", "career history",
    ],
    "education": ["education", "academic background", "education and training"],
    "skills": [
        "skills", "technical skills", "core competencies", "key skills",
        "skills and abilities", "areas of expertise",
    ],
    "projects": ["projects", "personal projects", "academic projects", "key projects"],
    "certifications": ["certifications", "certificates", "licenses and certifications"],
    "achievements": ["achievements", "awards", "honors", "awards and honors", "accomplishments"],
}


def detect_sections(text: str) -> dict:
    return scan_sections(text, SECTION_SYNONYMS)
