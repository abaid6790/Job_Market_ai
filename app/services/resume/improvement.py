"""
Resume improvement analysis, deterministic layer.

This always works with zero AI configuration — section completeness,
weak-bullet detection, and (when a job is provided) missing keywords/
skills are all real, explainable checks over the resume's own actual
content. Never invents experience, education, certifications, or
achievements the user hasn't stated — it only ever points at gaps or
phrasing in what's already there.

An optional AI-generated layer (ai_suggestions.py) can add qualitative
prose suggestions on top of this, following the same graceful-degradation
pattern as Phase 9's assistant — but this deterministic baseline is the
feature that's guaranteed to produce real, useful output regardless of
whether any provider is configured.
"""
import re

from app.services.matching.keyword_coverage import keyword_coverage_detail

EXPECTED_SECTIONS = ["summary", "experience", "education", "skills"]

STRONG_ACTION_VERBS = {
    "led", "built", "designed", "implemented", "developed", "managed", "created",
    "improved", "increased", "reduced", "automated", "launched", "optimized",
    "architected", "delivered", "achieved", "streamlined", "spearheaded",
    "established", "directed", "coordinated", "executed", "analyzed", "resolved",
    "enhanced", "generated", "negotiated", "mentored", "trained", "presented",
    "researched", "devised", "engineered", "deployed", "migrated", "refactored",
    "debugged", "tested", "documented", "collaborated", "facilitated", "initiated",
    "pioneered", "transformed", "scaled", "consolidated", "standardized",
    "accelerated", "boosted", "drove", "authored", "owned", "shipped",
}

MIN_BULLET_LENGTH = 25
_DIGIT_RE = re.compile(r"\d")


def _missing_sections(resume):
    present = {s.section_type for s in resume.sections.all()}
    return [s for s in EXPECTED_SECTIONS if s not in present]


def _split_bullets(description):
    if not description:
        return []
    lines = [l.strip(" -\u2022\u2013\t") for l in description.split("\n")]
    return [l for l in lines if l]


def _analyze_bullet(bullet):
    issues = []
    first_word = bullet.split(" ", 1)[0].lower().strip(".,;:") if bullet else ""
    if first_word not in STRONG_ACTION_VERBS:
        issues.append('Consider starting with a strong action verb (e.g. "Built", "Led", "Improved").')
    if not _DIGIT_RE.search(bullet):
        issues.append('Consider adding a measurable outcome or number (e.g. "reduced load time by 30%").')
    if len(bullet) < MIN_BULLET_LENGTH:
        issues.append("This line is quite short — consider adding more concrete detail.")
    return issues


def _weak_bullets(resume):
    weak = []
    for exp in resume.experiences.all():
        for bullet in _split_bullets(exp.description):
            issues = _analyze_bullet(bullet)
            if issues:
                weak.append({"text": bullet, "issues": issues, "experience": exp.job_title or exp.company})
    return weak


def _missing_keywords_and_skills(resume, job):
    if job is None:
        return None, None

    keyword_detail = keyword_coverage_detail(job.raw_text or "", resume.raw_text or "")
    missing_keywords = keyword_detail["missing"][:15] if keyword_detail else []

    required = {js.skill.name for js in job.job_skills.filter_by(requirement_level="required").all()}
    preferred = {js.skill.name for js in job.job_skills.filter_by(requirement_level="preferred").all()}
    resume_skills = {rs.skill.name for rs in resume.resume_skills.all()}

    missing_skills = {
        "critical": sorted(required - resume_skills),
        "important": sorted(preferred - resume_skills),
    }
    return missing_keywords, missing_skills


def analyze_resume(resume, job=None):
    missing_keywords, missing_skills = _missing_keywords_and_skills(resume, job)

    return {
        "missing_sections": _missing_sections(resume),
        "weak_bullets": _weak_bullets(resume),
        "missing_keywords": missing_keywords,
        "missing_skills": missing_skills,
        "job_context": {"id": job.id, "title": job.title} if job else None,
    }
