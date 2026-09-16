"""
Skill demand forecasting.

This is the feature most at risk of producing confident-sounding
nonsense, so the gating here is deliberately strict.

The spec is explicit: "Do not claim real-world growth percentages unless
calculated from actual collected data." A forecast is a claim about the
*future*, which is an even stronger claim than a historical growth rate —
so this requires MIN_MONTHS_OF_HISTORY months of data with
MIN_JOBS_PER_MONTH jobs each before it will project anything at all,
and even then it:

  - uses simple linear extrapolation over observed monthly demand (no
    pretence of a sophisticated model),
  - projects only ONE month ahead (short horizons are the only honest
    ones with this little data),
  - returns an explicit confidence band and a plain-language caveat,
  - names the method so nobody mistakes it for something it isn't.

In a typical fresh deployment this will correctly report insufficient
data. That is the expected and correct behaviour, not a bug.
"""
from collections import defaultdict

from app.extensions import db
from app.models import Job, JobSkill, Skill

MIN_MONTHS_OF_HISTORY = 3
MIN_JOBS_PER_MONTH = 3
MAX_FORECAST_SKILLS = 10

METHOD_NOTE = (
    "Projection uses simple linear extrapolation over observed monthly demand, "
    "one month ahead only. It is an estimate based on this deployment's own "
    "collected data — not a market prediction, and not based on any external "
    "data source."
)


def _monthly_demand_series():
    """Returns {month_key: {skill_id: pct_of_jobs}} plus jobs-per-month."""
    rows = (
        db.session.query(Job.created_at, JobSkill.skill_id, JobSkill.job_id)
        .join(JobSkill, JobSkill.job_id == Job.id)
        .filter(Job.status == "completed")
        .all()
    )

    jobs_by_month = defaultdict(set)
    skills_by_month_job = defaultdict(set)
    for created_at, skill_id, job_id in rows:
        month = created_at.strftime("%Y-%m")
        jobs_by_month[month].add(job_id)
        skills_by_month_job[(month, job_id)].add(skill_id)

    series = {}
    for month, job_ids in jobs_by_month.items():
        counts = defaultdict(int)
        for job_id in job_ids:
            for skill_id in skills_by_month_job[(month, job_id)]:
                counts[skill_id] += 1
        total = len(job_ids)
        series[month] = {sid: (count / total) * 100 for sid, count in counts.items()}

    return series, {m: len(ids) for m, ids in jobs_by_month.items()}


def _linear_projection(values):
    """Least-squares slope over evenly spaced points, projected one step
    ahead. Clamped to [0, 100] since it's a percentage of postings."""
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n

    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return mean_y, 0.0

    slope = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n)) / denominator
    intercept = mean_y - slope * mean_x
    projected = slope * n + intercept
    return max(0.0, min(100.0, projected)), slope


def forecast_skill_demand():
    series, jobs_per_month = _monthly_demand_series()

    qualifying_months = sorted(
        m for m, count in jobs_per_month.items() if count >= MIN_JOBS_PER_MONTH
    )

    if len(qualifying_months) < MIN_MONTHS_OF_HISTORY:
        return {
            "available": False,
            "reason": (
                f"Insufficient data — forecasting requires at least "
                f"{MIN_MONTHS_OF_HISTORY} months of history with "
                f"{MIN_JOBS_PER_MONTH}+ analyzed jobs each. This deployment currently "
                f"has {len(qualifying_months)} qualifying month(s). "
                "Keep analyzing jobs over time to unlock this — no projection is shown "
                "until there's genuinely enough data to base one on."
            ),
            "qualifying_months": len(qualifying_months),
            "months_required": MIN_MONTHS_OF_HISTORY,
        }

    months = qualifying_months[-6:]  # at most the last 6 qualifying months

    # Only forecast skills present in EVERY month used — a skill that
    # appeared once can't have a trend line fitted to it honestly.
    skill_ids = set(series[months[0]].keys())
    for month in months[1:]:
        skill_ids &= set(series[month].keys())

    if not skill_ids:
        return {
            "available": False,
            "reason": (
                "No single skill appears consistently across every month of available "
                "history, so there's no stable series to project from."
            ),
        }

    projections = []
    for skill_id in skill_ids:
        values = [series[m].get(skill_id, 0.0) for m in months]
        projected, slope = _linear_projection(values)
        current = values[-1]
        spread = max(values) - min(values)
        projections.append(
            {
                "skill_id": skill_id,
                "current_demand": round(current, 1),
                "projected_demand": round(projected, 1),
                "change": round(projected - current, 1),
                "slope_per_month": round(slope, 2),
                # Historical volatility as a plain confidence band — wider
                # spread in the observed data means a less trustworthy
                # projection, and we say so rather than hiding it.
                "volatility": round(spread, 1),
                "history": [round(v, 1) for v in values],
            }
        )

    skills_by_id = {s.id: s for s in Skill.query.filter(Skill.id.in_(skill_ids)).all()}
    for p in projections:
        skill = skills_by_id.get(p["skill_id"])
        p["skill_name"] = skill.name if skill else f"Skill #{p['skill_id']}"

    projections.sort(key=lambda p: p["change"], reverse=True)

    return {
        "available": True,
        "months_used": months,
        "jobs_per_month": {m: jobs_per_month[m] for m in months},
        "method_note": METHOD_NOTE,
        "rising": [p for p in projections if p["change"] > 0][:MAX_FORECAST_SKILLS],
        "falling": sorted(
            [p for p in projections if p["change"] < 0], key=lambda p: p["change"]
        )[:MAX_FORECAST_SKILLS],
        "stable": [p for p in projections if p["change"] == 0][:MAX_FORECAST_SKILLS],
    }
