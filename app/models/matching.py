from datetime import datetime

from app.extensions import db

GAP_CATEGORIES = ["critical", "important", "optional"]


class JobAnalysis(db.Model):
    """A resume-vs-job compatibility report. One row per (resume, job)
    pair — re-running the match updates the existing row in place rather
    than accumulating duplicate history, keeping "the" report for a given
    pair singular and easy to reason about."""

    __tablename__ = "job_analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)

    # Each sub-score is 0-100, or NULL when there isn't enough data to
    # compute it confidently (never fabricated as 0 or 100).
    overall_score = db.Column(db.Float, nullable=True)
    skills_score = db.Column(db.Float, nullable=True)
    experience_score = db.Column(db.Float, nullable=True)
    education_score = db.Column(db.Float, nullable=True)
    keyword_coverage_score = db.Column(db.Float, nullable=True)
    semantic_similarity_score = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship(
        "User", backref=db.backref("job_analyses", lazy="dynamic", cascade="all, delete-orphan")
    )
    resume = db.relationship(
        "Resume", backref=db.backref("job_analyses", lazy="dynamic", cascade="all, delete-orphan")
    )
    job = db.relationship(
        "Job", backref=db.backref("job_analyses", lazy="dynamic", cascade="all, delete-orphan")
    )

    skill_gaps = db.relationship(
        "SkillGap", backref="job_analysis", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("resume_id", "job_id", name="uq_resume_job_analysis"),
    )


class SkillGap(db.Model):
    __tablename__ = "skill_gaps"

    id = db.Column(db.Integer, primary_key=True)
    job_analysis_id = db.Column(
        db.Integer, db.ForeignKey("job_analyses.id"), nullable=False, index=True
    )
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)

    gap_category = db.Column(db.String(10), nullable=False)  # critical | important | optional
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    skill = db.relationship("Skill")
