"""
Portfolio project recommendations — deterministic template generation
over the user's real skill gaps, not an LLM-invented idea. Groups the
most urgent missing skills into small clusters and describes a concrete
project combining them, with difficulty/time estimated by how many
skills are involved.

This intentionally stays template-based rather than calling an AI
provider: it works identically with zero configuration, and every
technology named is drawn directly from real gap data — nothing
invented. A future phase could add an optional AI-enhanced variant
behind the same graceful-degradation pattern established in Phase 9,
without needing to change this deterministic baseline.
"""
from app.extensions import db
from app.models import Recommendation
from app.services.roadmap.gap_aggregator import gather_gap_skills

SKILLS_PER_PROJECT = 2
MAX_PROJECTS = 5

DIFFICULTY_BY_SKILL_COUNT = {1: "beginner", 2: "intermediate"}
TIME_BY_DIFFICULTY = {
    "beginner": "1-2 weeks",
    "intermediate": "2-4 weeks",
    "advanced": "4-6 weeks",
}


def _difficulty_for(skill_count):
    return DIFFICULTY_BY_SKILL_COUNT.get(skill_count, "advanced")


def _build_project(skill_names):
    difficulty = _difficulty_for(len(skill_names))
    if len(skill_names) <= 2:
        joined = " and ".join(skill_names)
    else:
        joined = ", ".join(skill_names[:-1]) + f", and {skill_names[-1]}"

    title = f"Build a project using {joined}"
    description = (
        f"Design and build a small project that puts {joined} into practice. "
        f"This is a real gap between your current skills and what your target "
        f"jobs are asking for — a focused project is one of the fastest ways to "
        f"close it and have something concrete to show for it."
    )

    return {
        "title": title,
        "description": description,
        "skills_involved": ", ".join(skill_names),
        "difficulty": difficulty,
        "estimated_time": TIME_BY_DIFFICULTY[difficulty],
        "suggested_technologies": ", ".join(skill_names),
    }


def generate_project_recommendations(user):
    """Returns a list of persisted Recommendation rows, replacing any
    previous ones for this user. Empty list if there's no gap data yet."""
    gap_skills = gather_gap_skills(user)
    if not gap_skills:
        return []

    Recommendation.query.filter_by(user_id=user.id, recommendation_type="project").delete()

    skill_names = [skill.name for skill, _category in gap_skills]
    chunks = [
        skill_names[i : i + SKILLS_PER_PROJECT]
        for i in range(0, len(skill_names), SKILLS_PER_PROJECT)
    ][:MAX_PROJECTS]

    recommendations = []
    for chunk in chunks:
        data = _build_project(chunk)
        rec = Recommendation(user_id=user.id, recommendation_type="project", **data)
        db.session.add(rec)
        recommendations.append(rec)

    db.session.commit()
    return recommendations
