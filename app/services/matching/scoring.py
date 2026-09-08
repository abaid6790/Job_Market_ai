"""
Individual sub-score calculations and their weighted combination into an
overall match score.

Every function here returns None (not 0, not 100) when there isn't enough
data to compute a confident answer — e.g. a job with no detected
experience requirement, or a profile with no education level set. The
overall score only weighs the sub-scores that are actually available,
renormalizing weights among them, so a handful of missing data points
never silently drags the overall score toward zero.
"""

REQUIRED_SKILL_WEIGHT = 0.7
PREFERRED_SKILL_WEIGHT = 0.3

EDUCATION_ORDER = {"high_school": 1, "associate": 2, "bachelor": 3, "master": 4, "phd": 5}

DEFAULT_OVERALL_WEIGHTS = {
    "skills": 0.40,
    "semantic": 0.20,
    "keyword": 0.15,
    "experience": 0.15,
    "education": 0.10,
}


def skills_score(required_ids: set, preferred_ids: set, user_skill_ids: set) -> float | None:
    if not required_ids and not preferred_ids:
        return None  # the job has no detected skills at all — nothing to score against

    required_pct = None
    preferred_pct = None

    if required_ids:
        matched = required_ids & user_skill_ids
        required_pct = (len(matched) / len(required_ids)) * 100

    if preferred_ids:
        matched = preferred_ids & user_skill_ids
        preferred_pct = (len(matched) / len(preferred_ids)) * 100

    if required_pct is not None and preferred_pct is not None:
        return round(required_pct * REQUIRED_SKILL_WEIGHT + preferred_pct * PREFERRED_SKILL_WEIGHT, 1)
    if required_pct is not None:
        return round(required_pct, 1)
    return round(preferred_pct, 1)


def experience_score(user_years, job_min_years) -> float | None:
    if user_years is None or job_min_years is None:
        return None
    if job_min_years <= 0:
        return 100.0
    if user_years >= job_min_years:
        return 100.0
    return round((user_years / job_min_years) * 100, 1)


def education_score(user_level: str, job_level: str) -> float | None:
    """Only computed when both levels sit on the strict ordinal ladder
    (high_school < associate < bachelor < master < phd). Non-ordinal
    levels like bootcamp/self_taught/other are real and valid, but not
    confidently comparable on a single scale — returning None here rather
    than guessing avoids penalizing (or over-crediting) a candidate for a
    credential the ladder can't fairly place."""
    if user_level not in EDUCATION_ORDER or job_level not in EDUCATION_ORDER:
        return None
    return 100.0 if EDUCATION_ORDER[user_level] >= EDUCATION_ORDER[job_level] else 0.0


def overall_score(sub_scores: dict, weights: dict = None) -> float | None:
    weights = weights or DEFAULT_OVERALL_WEIGHTS
    available = {k: v for k, v in sub_scores.items() if v is not None}
    if not available:
        return None
    total_weight = sum(weights[k] for k in available)
    if total_weight == 0:
        return None
    weighted_sum = sum(available[k] * weights[k] for k in available)
    return round(weighted_sum / total_weight, 1)
