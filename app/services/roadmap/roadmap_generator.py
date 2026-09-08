"""
Career roadmap generation — deterministic, not AI-generated.

One skill per month, ordered by urgency (critical gaps first, then
important, then optional), capped at MAX_MONTHS. This is a rule-based
pacing over real gap data (Phase 6), not an invented plan — consistent
with the project's "cheapest suitable method" philosophy and the spec's
explicit instruction not to fabricate.

Regenerating an existing roadmap preserves progress on any skill that
appears in both the old and new roadmap (a user marking "Docker" as
"learning" shouldn't get reset to "not_started" just because they ran a
new match report) — only skills that are new to the roadmap start at
"not_started".
"""
from app.extensions import db
from app.models import CareerRoadmap, RoadmapSkill, JobAnalysis
from app.services.roadmap.gap_aggregator import gather_gap_skills

MAX_MONTHS = 12


def generate_roadmap(user):
    """Returns the (created-or-updated) CareerRoadmap, or None if there's
    no gap data yet to build one from."""
    gap_skills = gather_gap_skills(user)
    if not gap_skills:
        return None

    gap_skills = gap_skills[:MAX_MONTHS]

    roadmap = CareerRoadmap.query.filter_by(user_id=user.id).first()
    previous_status = {}

    if roadmap is None:
        roadmap = CareerRoadmap(user_id=user.id)
        db.session.add(roadmap)
        db.session.flush()
    else:
        for rs in roadmap.roadmap_skills.all():
            previous_status[rs.skill_id] = rs.status
        RoadmapSkill.query.filter_by(roadmap_id=roadmap.id).delete()

    profile = user.profile
    roadmap.target_role = profile.target_role if profile else None
    roadmap.based_on_match_count = JobAnalysis.query.filter_by(user_id=user.id).count()

    for month_number, (skill, category) in enumerate(gap_skills, start=1):
        db.session.add(
            RoadmapSkill(
                roadmap_id=roadmap.id,
                skill_id=skill.id,
                month_number=month_number,
                source_gap_category=category,
                status=previous_status.get(skill.id, "not_started"),
            )
        )

    db.session.commit()
    return roadmap
