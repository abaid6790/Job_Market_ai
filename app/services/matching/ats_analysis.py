"""
ATS-style analysis — reuses the real, already-computed match report data
(Phase 6) and adds a few additional deterministic checks that are
specifically ATS-flavored rather than "how good a fit is this candidate"
(title alignment, section structure, formatting problems). Every check
here is a real, explainable heuristic over real data — no AI call, no
fabricated score. Per the spec, callers must always show the disclaimer
that this is an estimate, not a specific employer's actual ATS.

DISCLAIMER (render this wherever ATS results are shown):
"This is an estimated ATS-style analysis and is not an exact
representation of any specific employer's ATS."
"""
import re

from app.services.matching.keyword_coverage import keyword_coverage_detail

ATS_DISCLAIMER = (
    "This is an estimated ATS-style analysis and is not an exact "
    "representation of any specific employer's ATS."
)

EXPECTED_SECTIONS = ["summary", "experience", "education", "skills"]
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
_TITLE_STOPWORDS = {"senior", "junior", "lead", "staff", "principal", "the", "and", "of", "for"}


def _title_words(title):
    if not title:
        return set()
    words = {w.lower() for w in _WORD_RE.findall(title)}
    return words - _TITLE_STOPWORDS


def _job_title_alignment(resume_text, job_title):
    words = _title_words(job_title)
    if not words or not resume_text:
        return {"available": False}

    resume_lower = resume_text.lower()
    matched = [w for w in words if w in resume_lower]
    return {
        "available": True,
        "matched_words": matched,
        "coverage_pct": round((len(matched) / len(words)) * 100, 1),
    }


def _section_structure(resume):
    present = {s.section_type for s in resume.sections.all()}
    missing = [s for s in EXPECTED_SECTIONS if s not in present]
    return {
        "present": sorted(present & set(EXPECTED_SECTIONS)),
        "missing": missing,
    }


def _formatting_problems(resume):
    problems = []
    if not resume.extracted_email:
        problems.append("No email address detected — make sure your contact info is in plain text, not an image.")
    if not resume.extracted_name:
        problems.append("Couldn't confidently detect your name at the top of the resume.")
    if resume.experiences.count() == 0:
        problems.append("No work experience entries detected — check that experience is in a dedicated, clearly labeled section.")
    if resume.resume_skills.count() == 0:
        problems.append("No recognized skills detected — consider adding an explicit Skills section.")
    if resume.raw_text and len(resume.raw_text) < 400:
        problems.append("Resume text is unusually short — ATS systems may be missing content from images, tables, or unusual formatting.")
    return problems


def compute_ats_analysis(resume, job):
    keyword_detail = keyword_coverage_detail(job.raw_text or "", resume.raw_text or "")
    required_skills = [js.skill.name for js in job.job_skills.filter_by(requirement_level="required").all()]
    resume_skill_names = {rs.skill.name for rs in resume.resume_skills.all()}
    missing_required_skills = [s for s in required_skills if s not in resume_skill_names]

    return {
        "disclaimer": ATS_DISCLAIMER,
        "keyword_coverage": keyword_detail,
        "required_skills": {
            "total": len(required_skills),
            "matched": [s for s in required_skills if s in resume_skill_names],
            "missing": missing_required_skills,
        },
        "job_title_alignment": _job_title_alignment(resume.raw_text or "", job.title or ""),
        "section_structure": _section_structure(resume),
        "formatting_problems": _formatting_problems(resume),
    }
