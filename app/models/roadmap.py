from datetime import datetime

from app.extensions import db

ROADMAP_SKILL_STATUSES = ["not_started", "learning", "completed"]
LEARNING_RESOURCE_TYPES = ["documentation", "tutorial", "course", "book", "practice_platform"]
DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced"]


class CareerRoadmap(db.Model):
    """One active roadmap per user — regenerating updates this same row
    and its RoadmapSkill children in place (same pattern as JobAnalysis),
    rather than accumulating history."""

    __tablename__ = "career_roadmaps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)
    target_role = db.Column(db.String(150), nullable=True)
    based_on_match_count = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship(
        "User", backref=db.backref("career_roadmap", uselist=False, cascade="all, delete-orphan")
    )
    roadmap_skills = db.relationship(
        "RoadmapSkill",
        backref="roadmap",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="RoadmapSkill.month_number",
    )


class RoadmapSkill(db.Model):
    __tablename__ = "roadmap_skills"

    id = db.Column(db.Integer, primary_key=True)
    roadmap_id = db.Column(
        db.Integer, db.ForeignKey("career_roadmaps.id"), nullable=False, index=True
    )
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)

    month_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(15), default="not_started", nullable=False)
    source_gap_category = db.Column(db.String(10), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    skill = db.relationship("Skill")

    __table_args__ = (
        db.UniqueConstraint("roadmap_id", "skill_id", name="uq_roadmap_skill"),
    )


class LearningResource(db.Model):
    """Curated, admin-extendable resource links per skill. Only ever
    populated with real, stable official documentation URLs (or
    admin-added entries) — never a fabricated/guessed course link, per
    the spec's explicit instruction."""

    __tablename__ = "learning_resources"

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    resource_type = db.Column(db.String(20), default="documentation", nullable=False)
    is_curated = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    skill = db.relationship("Skill", backref=db.backref("learning_resources", lazy="dynamic"))


class Recommendation(db.Model):
    """A recommended portfolio project, built deterministically from the
    user's actual skill gaps (never an invented, unrelated project idea)."""

    __tablename__ = "recommendations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    recommendation_type = db.Column(db.String(20), default="project", nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    skills_involved = db.Column(db.String(300), nullable=True)
    difficulty = db.Column(db.String(15), nullable=True)
    estimated_time = db.Column(db.String(50), nullable=True)
    suggested_technologies = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User", backref=db.backref("recommendations", lazy="dynamic", cascade="all, delete-orphan")
    )
