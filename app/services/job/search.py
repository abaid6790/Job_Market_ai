"""
Job search, over the shared pool of completed Job records (both
individually analyzed and admin-imported) — the same aggregate dataset
Market Insights (Phase 5) already reads from. Job posting content isn't
personal data about whoever submitted it, so searching across everyone's
analyzed jobs is consistent with that established precedent; only the
submitting user's identity and any SavedJob notes stay private.
"""
from app.extensions import db
from app.models import Job, JobSkill

DEFAULT_PER_PAGE = 20


def search_jobs(
    query=None,
    location=None,
    remote_status=None,
    employment_type=None,
    max_experience=None,
    min_salary=None,
    skill_ids=None,
    page=1,
    per_page=DEFAULT_PER_PAGE,
):
    q = Job.query.filter(Job.status == "completed")

    if query:
        like = f"%{query.strip()}%"
        q = q.filter(db.or_(Job.title.ilike(like), Job.company.ilike(like)))

    if location:
        q = q.filter(Job.location.ilike(f"%{location.strip()}%"))

    if remote_status:
        q = q.filter(Job.remote_status == remote_status)

    if employment_type:
        q = q.filter(Job.employment_type == employment_type)

    if max_experience is not None:
        q = q.filter(
            db.or_(Job.experience_years_min.is_(None), Job.experience_years_min <= max_experience)
        )

    if min_salary is not None:
        q = q.filter(Job.salary_max.isnot(None), Job.salary_max >= min_salary)

    if skill_ids:
        q = q.join(JobSkill, JobSkill.job_id == Job.id).filter(JobSkill.skill_id.in_(skill_ids)).distinct()

    q = q.order_by(Job.created_at.desc())

    return q.paginate(page=page, per_page=per_page, error_out=False)
