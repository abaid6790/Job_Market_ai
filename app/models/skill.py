from datetime import datetime

from app.extensions import db


class SkillCategory(db.Model):
    __tablename__ = "skill_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    skills = db.relationship("Skill", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<SkillCategory {self.name}>"


class Skill(db.Model):
    """A canonical skill in the taxonomy.

    `normalized_name` is the lookup key used by the skill normalizer so that
    variations like "Python 3" / "python programming" resolve to one Skill,
    either by exact normalized match or via a SkillAlias row.
    """

    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    normalized_name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("skill_categories.id"), nullable=True, index=True
    )

    # Skills typed by users that don't match the taxonomy land here with no
    # category, awaiting admin triage — the taxonomy stays extendable
    # without needing a code change or blocking the user.
    is_user_suggested = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    aliases = db.relationship(
        "SkillAlias", backref="skill", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Skill {self.name}>"


class SkillAlias(db.Model):
    """A known alternate spelling/variant that maps to a canonical Skill."""

    __tablename__ = "skill_aliases"

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)
    alias = db.Column(db.String(120), nullable=False)
    normalized_alias = db.Column(db.String(120), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SkillAlias {self.alias} -> skill_id={self.skill_id}>"
