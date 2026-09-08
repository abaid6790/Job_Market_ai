import json
from datetime import datetime

from app.extensions import db

PROFICIENCY_LEVELS = ["beginner", "intermediate", "advanced", "expert"]
REMOTE_PREFERENCES = ["remote", "hybrid", "onsite", "flexible"]
EDUCATION_LEVELS = [
    "high_school",
    "associate",
    "bachelor",
    "master",
    "phd",
    "bootcamp",
    "self_taught",
    "other",
]


class UserProfile(db.Model):
    __tablename__ = "user_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True
    )

    location = db.Column(db.String(150), nullable=True)
    current_role = db.Column(db.String(150), nullable=True)
    target_role = db.Column(db.String(150), nullable=True)
    years_experience = db.Column(db.Integer, nullable=True)
    education_level = db.Column(db.String(30), nullable=True)
    remote_preference = db.Column(db.String(20), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    # Stored as JSON text for now (Phase 2 scope). Phase 5+ location/industry
    # analytics can migrate these to normalized lookup tables if needed.
    _preferred_industries = db.Column("preferred_industries", db.Text, nullable=True)
    _preferred_locations = db.Column("preferred_locations", db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship(
        "User", backref=db.backref("profile", uselist=False, cascade="all, delete-orphan")
    )

    @property
    def preferred_industries(self):
        return json.loads(self._preferred_industries) if self._preferred_industries else []

    @preferred_industries.setter
    def preferred_industries(self, values):
        cleaned = [v.strip() for v in values if v and v.strip()]
        self._preferred_industries = json.dumps(cleaned)

    @property
    def preferred_locations(self):
        return json.loads(self._preferred_locations) if self._preferred_locations else []

    @preferred_locations.setter
    def preferred_locations(self, values):
        cleaned = [v.strip() for v in values if v and v.strip()]
        self._preferred_locations = json.dumps(cleaned)

    def __repr__(self):
        return f"<UserProfile user_id={self.user_id}>"


class UserSkill(db.Model):
    __tablename__ = "user_skills"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)

    proficiency = db.Column(db.String(20), nullable=True)
    years_experience = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(20), default="manual", nullable=False)  # manual | resume
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User", backref=db.backref("user_skills", lazy="dynamic", cascade="all, delete-orphan")
    )
    skill = db.relationship("Skill", backref=db.backref("user_skills", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),
    )


class UserCertification(db.Model):
    __tablename__ = "user_certifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    name = db.Column(db.String(150), nullable=False)
    issuing_organization = db.Column(db.String(150), nullable=True)
    year_obtained = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User", backref=db.backref("certifications", lazy="dynamic", cascade="all, delete-orphan")
    )
