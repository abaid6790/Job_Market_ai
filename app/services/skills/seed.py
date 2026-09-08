"""
Idempotent taxonomy loader. Safe to run multiple times: existing
categories/skills/aliases are left untouched, only missing ones are added.
"""
from app.extensions import db
from app.models.skill import SkillCategory, Skill, SkillAlias
from app.services.skills.normalizer import normalize_text
from app.services.skills.seed_data import TAXONOMY


def seed_taxonomy() -> dict:
    stats = {"categories_added": 0, "skills_added": 0, "aliases_added": 0}

    for sort_order, entry in enumerate(TAXONOMY):
        cat_name = entry["category"]
        slug = normalize_text(cat_name).replace(" ", "-")

        category = SkillCategory.query.filter_by(name=cat_name).first()
        if not category:
            category = SkillCategory(name=cat_name, slug=slug, sort_order=sort_order)
            db.session.add(category)
            db.session.flush()
            stats["categories_added"] += 1

        for skill_entry in entry["skills"]:
            skill_name = skill_entry["name"]
            normalized = normalize_text(skill_name)

            skill = Skill.query.filter_by(normalized_name=normalized).first()
            if not skill:
                skill = Skill(
                    name=skill_name,
                    normalized_name=normalized,
                    category_id=category.id,
                    is_user_suggested=False,
                    is_active=True,
                )
                db.session.add(skill)
                db.session.flush()
                stats["skills_added"] += 1
            elif skill.category_id is None:
                # A previously user-suggested skill now matches a seeded
                # canonical entry — promote it into the taxonomy properly.
                skill.category_id = category.id
                skill.is_user_suggested = False

            for alias_text in skill_entry.get("aliases", []):
                normalized_alias = normalize_text(alias_text)
                if not normalized_alias or normalized_alias == normalized:
                    continue
                existing_alias = SkillAlias.query.filter_by(
                    normalized_alias=normalized_alias
                ).first()
                if not existing_alias:
                    db.session.add(
                        SkillAlias(
                            skill_id=skill.id,
                            alias=alias_text,
                            normalized_alias=normalized_alias,
                        )
                    )
                    stats["aliases_added"] += 1

    db.session.commit()
    return stats
