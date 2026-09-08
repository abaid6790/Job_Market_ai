"""
Resume-vs-job matching orchestrator.

Ties together skills/experience/education/keyword/semantic sub-scores,
the weighted overall score, and skill gap classification, then persists
the result. Re-running a match for the same (resume, job) pair updates
the existing report in place rather than accumulating duplicates.
"""
from app.extensions import db
from app.models import JobAnalysis, SkillGap, UserSkill
from app.services.matching.scoring import (
    skills_score,
    experience_score,
    education_score,
    overall_score,
)
from app.services.matching.semantic import semantic_similarity
from app.services.matching.keyword_coverage import keyword_coverage
from app.services.matching.skill_gap import compute_skill_gaps


def compute_match(user, resume, job) -> dict:
    profile = user.profile
    user_skill_ids = {us.skill_id for us in UserSkill.query.filter_by(user_id=user.id).all()}
    required_ids = {js.skill_id for js in job.job_skills.filter_by(requirement_level="required").all()}
    preferred_ids = {js.skill_id for js in job.job_skills.filter_by(requirement_level="preferred").all()}

    scores = {
        "skills": skills_score(required_ids, preferred_ids, user_skill_ids),
        "semantic": semantic_similarity(resume.raw_text or "", job.raw_text or ""),
        "keyword": keyword_coverage(job.raw_text or "", resume.raw_text or ""),
        "experience": experience_score(
            profile.years_experience if profile else None, job.experience_years_min
        ),
        "education": education_score(
            profile.education_level if profile else None, job.education_level
        ),
    }
    scores["overall"] = overall_score(scores)

    return {
        **scores,
        "required_ids": required_ids,
        "preferred_ids": preferred_ids,
        "user_skill_ids": user_skill_ids,
    }


def save_match_report(user, resume, job) -> JobAnalysis:
    match = compute_match(user, resume, job)
    gaps = compute_skill_gaps(match["required_ids"], match["preferred_ids"], match["user_skill_ids"])

    report = JobAnalysis.query.filter_by(resume_id=resume.id, job_id=job.id).first()
    if report is None:
        report = JobAnalysis(user_id=user.id, resume_id=resume.id, job_id=job.id)
        db.session.add(report)
        db.session.flush()
    else:
        SkillGap.query.filter_by(job_analysis_id=report.id).delete()

    report.overall_score = match["overall"]
    report.skills_score = match["skills"]
    report.experience_score = match["experience"]
    report.education_score = match["education"]
    report.keyword_coverage_score = match["keyword"]
    report.semantic_similarity_score = match["semantic"]
    db.session.flush()

    for category, skill_ids in gaps.items():
        for skill_id in skill_ids:
            db.session.add(
                SkillGap(job_analysis_id=report.id, skill_id=skill_id, gap_category=category)
            )

    db.session.commit()
    return report
