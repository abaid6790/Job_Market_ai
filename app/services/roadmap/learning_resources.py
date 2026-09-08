from app.extensions import db
from app.models import Skill, LearningResource
from app.services.roadmap.learning_resource_seed import CURATED_DOCUMENTATION


def get_resources_for_skill(skill_id):
    return LearningResource.query.filter_by(skill_id=skill_id).all()


def seed_learning_resources():
    """Idempotent — safe to re-run. Only adds resources for skills that
    exist in the taxonomy and don't already have a curated entry for
    that exact URL."""
    added = 0
    for skill_name, (title, url) in CURATED_DOCUMENTATION.items():
        skill = Skill.query.filter_by(name=skill_name).first()
        if not skill:
            continue
        existing = LearningResource.query.filter_by(skill_id=skill.id, url=url).first()
        if existing:
            continue
        db.session.add(
            LearningResource(
                skill_id=skill.id,
                title=title,
                url=url,
                resource_type="documentation",
                is_curated=True,
            )
        )
        added += 1
    db.session.commit()
    return added
