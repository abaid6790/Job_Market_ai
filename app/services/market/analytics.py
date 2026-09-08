"""
Market analytics.

Aggregates across ALL completed Job rows in the system (both individually
pasted/uploaded by users and admin-imported datasets) — job posting
content isn't personal data about the submitting user, so this aggregate
view doesn't violate per-user data isolation the way resumes/profiles do.

Every statistic here follows one rule: if there isn't enough data to say
something meaningful, say so explicitly rather than showing a number that
looks precise but isn't. Thresholds are named constants below so they're
easy to find and adjust as the dataset grows.
"""
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median

from app.extensions import db
from app.models import Job, JobSkill, Skill, SkillCategory

MIN_JOBS_FOR_SALARY_STATS = 3
MIN_JOBS_FOR_EXPERIENCE_STATS = 3
MIN_MONTHS_FOR_TRENDS = 2
MIN_JOBS_PER_MONTH_FOR_TRENDS = 2

EXPERIENCE_BUCKETS = [
    ("0-2 years", 0, 2),
    ("3-5 years", 3, 5),
    ("6-10 years", 6, 10),
    ("10+ years", 11, None),
]


def _completed_jobs_query():
    return Job.query.filter_by(status="completed")


def total_jobs_analyzed() -> int:
    return _completed_jobs_query().count()


def skill_demand(limit: int = 20) -> list[dict]:
    """Skill frequency and demand percentage across all analyzed jobs."""
    total = total_jobs_analyzed()
    if total == 0:
        return []

    # Count distinct jobs per skill (a skill mentioned twice in one job
    # still counts once — "demand" means "appears in this many postings").
    rows = (
        db.session.query(JobSkill.skill_id, db.func.count(db.func.distinct(JobSkill.job_id)))
        .join(Job, Job.id == JobSkill.job_id)
        .filter(Job.status == "completed")
        .group_by(JobSkill.skill_id)
        .order_by(db.func.count(db.func.distinct(JobSkill.job_id)).desc())
        .limit(limit)
        .all()
    )

    results = []
    for skill_id, count in rows:
        skill = db.session.get(Skill, skill_id)
        if not skill:
            continue
        results.append(
            {
                "skill": skill,
                "count": count,
                "percentage": round((count / total) * 100, 1),
            }
        )
    return results


def skill_cooccurrence(limit: int = 15) -> list[dict]:
    """Pairs of skills that most frequently appear together in the same job."""
    job_skills = (
        db.session.query(JobSkill.job_id, JobSkill.skill_id)
        .join(Job, Job.id == JobSkill.job_id)
        .filter(Job.status == "completed")
        .all()
    )

    skills_by_job = defaultdict(set)
    for job_id, skill_id in job_skills:
        skills_by_job[job_id].add(skill_id)

    pair_counts = Counter()
    for skill_ids in skills_by_job.values():
        sorted_ids = sorted(skill_ids)
        for i in range(len(sorted_ids)):
            for j in range(i + 1, len(sorted_ids)):
                pair_counts[(sorted_ids[i], sorted_ids[j])] += 1

    top_pairs = pair_counts.most_common(limit)
    if not top_pairs:
        return []

    skill_ids_needed = {sid for pair, _ in top_pairs for sid in pair}
    skills_by_id = {s.id: s for s in Skill.query.filter(Skill.id.in_(skill_ids_needed)).all()}

    results = []
    for (skill_id_a, skill_id_b), count in top_pairs:
        skill_a = skills_by_id.get(skill_id_a)
        skill_b = skills_by_id.get(skill_id_b)
        if not skill_a or not skill_b:
            continue
        results.append({"skill_a": skill_a, "skill_b": skill_b, "count": count})
    return results


def skill_trends(top_n: int = 10) -> dict:
    """Month-over-month skill demand change, only if there's genuinely
    enough historical spread to say anything — otherwise flags insufficient
    data rather than fabricating a growth percentage from one snapshot."""
    rows = (
        db.session.query(Job.created_at, JobSkill.skill_id, JobSkill.job_id)
        .join(JobSkill, JobSkill.job_id == Job.id)
        .filter(Job.status == "completed")
        .all()
    )

    if not rows:
        return {"available": False, "reason": "No analyzed jobs yet."}

    jobs_by_month = defaultdict(set)
    skills_by_month_job = defaultdict(set)
    for created_at, skill_id, job_id in rows:
        month_key = created_at.strftime("%Y-%m")
        jobs_by_month[month_key].add(job_id)
        skills_by_month_job[(month_key, job_id)].add(skill_id)

    months = sorted(jobs_by_month.keys())
    qualifying_months = [m for m in months if len(jobs_by_month[m]) >= MIN_JOBS_PER_MONTH_FOR_TRENDS]

    if len(qualifying_months) < MIN_MONTHS_FOR_TRENDS:
        return {
            "available": False,
            "reason": (
                f"Trend data needs at least {MIN_MONTHS_FOR_TRENDS} months with "
                f"{MIN_JOBS_PER_MONTH_FOR_TRENDS}+ analyzed jobs each. "
                "Keep analyzing jobs over time to unlock this."
            ),
        }

    latest_month, previous_month = qualifying_months[-1], qualifying_months[-2]

    def _skill_counts_for_month(month):
        counts = Counter()
        for job_id in jobs_by_month[month]:
            for skill_id in skills_by_month_job[(month, job_id)]:
                counts[skill_id] += 1
        return counts

    latest_counts = _skill_counts_for_month(latest_month)
    previous_counts = _skill_counts_for_month(previous_month)
    latest_total = len(jobs_by_month[latest_month])
    previous_total = len(jobs_by_month[previous_month])

    all_skill_ids = set(latest_counts) | set(previous_counts)
    skills_by_id = {s.id: s for s in Skill.query.filter(Skill.id.in_(all_skill_ids)).all()}

    trend_rows = []
    for skill_id in all_skill_ids:
        skill = skills_by_id.get(skill_id)
        if not skill:
            continue
        latest_pct = (latest_counts.get(skill_id, 0) / latest_total) * 100
        previous_pct = (previous_counts.get(skill_id, 0) / previous_total) * 100
        change = round(latest_pct - previous_pct, 1)
        trend_rows.append(
            {
                "skill": skill,
                "current_demand": round(latest_pct, 1),
                "previous_demand": round(previous_pct, 1),
                "change": change,
            }
        )

    trend_rows.sort(key=lambda r: r["change"], reverse=True)

    return {
        "available": True,
        "latest_month": latest_month,
        "previous_month": previous_month,
        "increasing": [r for r in trend_rows if r["change"] > 0][:top_n],
        "decreasing": sorted(
            [r for r in trend_rows if r["change"] < 0], key=lambda r: r["change"]
        )[:top_n],
    }


def top_titles(limit: int = 15) -> list[dict]:
    rows = _completed_jobs_query().filter(Job.title.isnot(None)).with_entities(Job.title).all()
    if not rows:
        return []
    counts = Counter(title.strip() for (title,) in rows if title and title.strip())
    return [{"title": title, "count": count} for title, count in counts.most_common(limit)]


def location_distribution(limit: int = 15) -> list[dict]:
    rows = _completed_jobs_query().filter(Job.location.isnot(None)).with_entities(Job.location).all()
    if not rows:
        return []
    counts = Counter(loc.strip() for (loc,) in rows if loc and loc.strip())
    total = sum(counts.values())
    return [
        {"location": loc, "count": count, "percentage": round((count / total) * 100, 1)}
        for loc, count in counts.most_common(limit)
    ]


def remote_distribution() -> dict:
    total = total_jobs_analyzed()
    if total == 0:
        return {}
    rows = _completed_jobs_query().with_entities(Job.remote_status).all()
    counts = Counter(status for (status,) in rows)
    return {
        status: {"count": counts.get(status, 0), "percentage": round((counts.get(status, 0) / total) * 100, 1)}
        for status in ("remote", "hybrid", "onsite", "unknown")
    }


def employment_type_distribution() -> dict:
    total = total_jobs_analyzed()
    if total == 0:
        return {}
    rows = _completed_jobs_query().with_entities(Job.employment_type).all()
    counts = Counter(t for (t,) in rows)
    return {
        etype: {"count": counts.get(etype, 0), "percentage": round((counts.get(etype, 0) / total) * 100, 1)}
        for etype in ("full_time", "part_time", "contract", "internship", "temporary", "unknown")
    }


def education_distribution() -> dict:
    total = total_jobs_analyzed()
    if total == 0:
        return {}
    rows = _completed_jobs_query().with_entities(Job.education_level).all()
    counts = Counter(level for (level,) in rows if level)
    known_total = sum(counts.values())
    if known_total == 0:
        return {"available": False}
    return {
        "available": True,
        "breakdown": [
            {"level": level, "count": count, "percentage": round((count / known_total) * 100, 1)}
            for level, count in counts.most_common()
        ],
        "unspecified_count": total - known_total,
    }


def experience_distribution() -> dict:
    rows = (
        _completed_jobs_query()
        .filter(Job.experience_years_min.isnot(None))
        .with_entities(Job.experience_years_min)
        .all()
    )
    if len(rows) < MIN_JOBS_FOR_EXPERIENCE_STATS:
        return {
            "available": False,
            "reason": (
                f"Insufficient data — need at least {MIN_JOBS_FOR_EXPERIENCE_STATS} jobs "
                "with a detected experience requirement."
            ),
        }

    bucket_counts = {label: 0 for label, _, _ in EXPERIENCE_BUCKETS}
    for (years,) in rows:
        for label, lo, hi in EXPERIENCE_BUCKETS:
            if years >= lo and (hi is None or years <= hi):
                bucket_counts[label] += 1
                break

    total = len(rows)
    return {
        "available": True,
        "total_with_data": total,
        "breakdown": [
            {"bucket": label, "count": bucket_counts[label], "percentage": round((bucket_counts[label] / total) * 100, 1)}
            for label, _, _ in EXPERIENCE_BUCKETS
        ],
    }


def salary_stats(currency: str = "USD", period: str = "year") -> dict:
    """Salary stats, restricted to one currency and one pay period at a
    time so min/max/median are never computed by mixing incompatible
    units (e.g. hourly GBP with annual USD)."""
    rows = (
        _completed_jobs_query()
        .filter(
            Job.salary_min.isnot(None),
            Job.salary_currency == currency,
            Job.salary_period == period,
        )
        .with_entities(Job.salary_min, Job.salary_max)
        .all()
    )

    if len(rows) < MIN_JOBS_FOR_SALARY_STATS:
        return {
            "available": False,
            "reason": (
                f"Insufficient data — need at least {MIN_JOBS_FOR_SALARY_STATS} jobs with "
                f"a detected {currency}/{period} salary."
            ),
            "sample_size": len(rows),
        }

    midpoints = [((lo or 0) + (hi or lo)) / 2 for lo, hi in rows]
    mins = [lo for lo, _ in rows]
    maxes = [hi if hi is not None else lo for lo, hi in rows]

    return {
        "available": True,
        "currency": currency,
        "period": period,
        "sample_size": len(rows),
        "min": min(mins),
        "max": max(maxes),
        "median": round(median(midpoints)),
        "average": round(sum(midpoints) / len(midpoints)),
    }


def role_analytics(title_query: str) -> dict:
    """Aggregate stats for jobs whose title contains the given query
    (case-insensitive substring match — deliberately simple rather than a
    fuzzy/ML title-normalization system that could quietly misclassify)."""
    query = title_query.strip().lower()
    if not query:
        return {"available": False, "reason": "No role specified."}

    matching_jobs = (
        _completed_jobs_query()
        .filter(db.func.lower(Job.title).contains(query))
        .all()
    )

    if not matching_jobs:
        return {"available": False, "reason": f'No analyzed jobs found matching "{title_query}".'}

    job_ids = [j.id for j in matching_jobs]
    total = len(job_ids)

    skill_rows = (
        db.session.query(JobSkill.skill_id, db.func.count(db.func.distinct(JobSkill.job_id)))
        .filter(JobSkill.job_id.in_(job_ids))
        .group_by(JobSkill.skill_id)
        .order_by(db.func.count(db.func.distinct(JobSkill.job_id)).desc())
        .limit(15)
        .all()
    )
    top_skills = []
    for skill_id, count in skill_rows:
        skill = db.session.get(Skill, skill_id)
        if skill:
            top_skills.append({"skill": skill, "count": count, "percentage": round((count / total) * 100, 1)})

    experience_values = [j.experience_years_min for j in matching_jobs if j.experience_years_min is not None]
    avg_experience = round(sum(experience_values) / len(experience_values), 1) if experience_values else None

    salary_values = [
        ((j.salary_min or 0) + (j.salary_max or j.salary_min)) / 2
        for j in matching_jobs
        if j.salary_min is not None and j.salary_currency == "USD" and j.salary_period == "year"
    ]
    avg_salary = round(sum(salary_values) / len(salary_values)) if len(salary_values) >= MIN_JOBS_FOR_SALARY_STATS else None

    return {
        "available": True,
        "query": title_query,
        "job_count": total,
        "top_skills": top_skills,
        "avg_experience_years": avg_experience,
        "avg_salary_usd_year": avg_salary,
        "avg_salary_sample_size": len(salary_values),
    }
