from datetime import datetime

from app.extensions import db

RESUME_STATUSES = ["pending", "processing", "completed", "failed"]
SECTION_TYPES = [
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "achievements",
    "other",
]


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # pdf | docx | txt
    file_size_bytes = db.Column(db.Integer, nullable=False)

    # Best-effort extracted contact info (structured, validated — never
    # trusted blindly; the raw text is always kept alongside for reference).
    extracted_name = db.Column(db.String(150), nullable=True)
    extracted_email = db.Column(db.String(255), nullable=True)
    extracted_phone = db.Column(db.String(50), nullable=True)
    linkedin_url = db.Column(db.String(255), nullable=True)
    github_url = db.Column(db.String(255), nullable=True)
    portfolio_url = db.Column(db.String(255), nullable=True)

    raw_text = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default="pending", nullable=False)
    error_message = db.Column(db.String(500), nullable=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship(
        "User", backref=db.backref("resumes", lazy="dynamic", cascade="all, delete-orphan")
    )

    sections = db.relationship(
        "ResumeSection",
        backref="resume",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ResumeSection.order_index",
    )
    experiences = db.relationship(
        "ResumeExperience",
        backref="resume",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ResumeExperience.order_index",
    )
    education_entries = db.relationship(
        "ResumeEducation",
        backref="resume",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ResumeEducation.order_index",
    )
    resume_skills = db.relationship(
        "ResumeSkill", backref="resume", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Resume {self.original_filename} user_id={self.user_id}>"


class ResumeSection(db.Model):
    __tablename__ = "resume_sections"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, index=True)
    section_type = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, default=0, nullable=False)


class ResumeExperience(db.Model):
    __tablename__ = "resume_experiences"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, index=True)

    job_title = db.Column(db.String(150), nullable=True)
    company = db.Column(db.String(150), nullable=True)
    location = db.Column(db.String(150), nullable=True)
    start_date = db.Column(db.String(30), nullable=True)  # free text: resumes rarely use ISO dates
    end_date = db.Column(db.String(30), nullable=True)
    is_current = db.Column(db.Boolean, default=False, nullable=False)
    description = db.Column(db.Text, nullable=True)
    order_index = db.Column(db.Integer, default=0, nullable=False)


class ResumeEducation(db.Model):
    __tablename__ = "resume_education"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, index=True)

    institution = db.Column(db.String(200), nullable=True)
    degree = db.Column(db.String(150), nullable=True)
    field_of_study = db.Column(db.String(150), nullable=True)
    start_date = db.Column(db.String(30), nullable=True)
    end_date = db.Column(db.String(30), nullable=True)
    order_index = db.Column(db.Integer, default=0, nullable=False)


class ResumeSkill(db.Model):
    __tablename__ = "resume_skills"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id"), nullable=False, index=True)
    raw_text = db.Column(db.String(150), nullable=True)  # the exact phrase matched in the resume
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    skill = db.relationship("Skill")

    __table_args__ = (
        db.UniqueConstraint("resume_id", "skill_id", name="uq_resume_skill"),
    )
