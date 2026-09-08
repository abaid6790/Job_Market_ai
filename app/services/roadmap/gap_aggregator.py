"""
Aggregates skill gaps across ALL of a user's resume-job match reports
(Phase 6) into one deduplicated, prioritized list — the real data basis
for both the career roadmap and project recommendations in this phase.

A skill that shows up as "critical" in one match and "important" in
another keeps its more urgent classification (critical), since that
reflects genuine unmet requirements across the jobs the user cares about.
"""
from app.models import JobAnalysis

CATEGORY_PRIORITY = {"critical": 0, "important": 1, "optional": 2}


def gather_gap_skills(user):
    """Returns an ordered list of (skill, category) tuples, most urgent
    first, deduplicated by skill. Empty if the user has no match reports
    with any gaps yet — callers must treat that as insufficient data,
    not silently fall back to guessing."""
    reports = JobAnalysis.query.filter_by(user_id=user.id).all()
    if not reports:
        return []

    best_category = {}
    skill_objects = {}

    for report in reports:
        for gap in report.skill_gaps.all():
            current = best_category.get(gap.skill_id)
            if current is None or CATEGORY_PRIORITY[gap.gap_category] < CATEGORY_PRIORITY[current]:
                best_category[gap.skill_id] = gap.gap_category
                skill_objects[gap.skill_id] = gap.skill

    ordered = sorted(best_category.items(), key=lambda item: CATEGORY_PRIORITY[item[1]])
    return [(skill_objects[skill_id], category) for skill_id, category in ordered]
