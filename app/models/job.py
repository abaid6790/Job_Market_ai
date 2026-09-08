from datetime import datetime

from app.extensions import db

JOB_STATUSES = ["pending", "processing", "completed", "failed"]
REMOTE_STATUSES = ["remote", "hybrid", "onsite", "unknown"]
EMPLOYMENT_TYPES = ["full_time", "part_time", "contract", "internship", "temporary", "unknown"]
SKILL_REQUIREMENT_LEVELS = ["required", "preferred"]


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=True)
    company = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    remote_status = db.Column(db.String(20), default="unknown", nullable=False)
    employment_type = db.Column(db.String(20), default="unknown", nullable=False)
    industry = db.Column(db.String(150), nullable=True)

    salary_min = db.Column(db.Integer, nullable=True)
    salary_max = db.Column(db.Integer, nullable=True)
    salary_currency = db.Column(db.String(10), nullable=True)
    salary_period = db.Column(db.String(10), nullable=True)  # year | hour | month

    experience_years_min = db.Column(db.Integer, nullable=True)
    experience_years_max = db.Column(db.Integer, nullable=True)

    education_level = db.Column(db.String(30), nullable=True)  # matches profile EDUCATION_LEVELS
    education_requirement_text = db.Column(db.String(300), nullable=True)

    source = db.Column(db.String(10), default="pasted", nullable=False)  # pasted | uploaded
    original_filename = db.Column(db.String(255), nullable=True)
    raw_text = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default="pending", nullable=False)
    error_message = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship(
        "User", backref=db.backref("jobs", lazy="dynamic", cascade="all, delete-orphan")
    )

    sections = db.relationship(
        "JobSection",
        backref="job",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="JobSection.order_index",
    )
    job_skills = db.relationship(
        "JobSkill", backref="job", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Job {self.title!r} @ {self.company!r} user_id={self.user_id}>"


class JobSection(db.Model):
    __tablename__ = "job_sections"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    section_type = db.Column(db.String(30), nullable=False)
    content = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, default=0, nullable=False)


class JobSkill(db.Model):
    __tablename__ = "job_skills"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)
    requirement_level = db.Column(db.String(10), default="required", nullable=False)
    raw_text = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    skill = db.relationship("Skill")

    __table_args__ = (
        db.UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),
    )
