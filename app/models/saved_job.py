from datetime import datetime

from app.extensions import db

SAVED_JOB_STATUSES = ["saved", "applied", "interview", "offer", "rejected"]


class SavedJob(db.Model):
    """A user's bookmark of a Job, with private notes and application
    status. One row per (user, job) pair — re-saving an already-saved job
    is a no-op rather than a duplicate, and updating status/notes updates
    this same row (so "Saved Jobs" and the "Application Tracker" are two
    views over one underlying record, per the spec's own description of
    the tracker as "lightweight" rather than a separate subsystem).
    """

    __tablename__ = "saved_jobs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)

    status = db.Column(db.String(10), default="saved", nullable=False)
    notes = db.Column(db.Text, nullable=True)
    application_date = db.Column(db.Date, nullable=True)
    interview_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship(
        "User", backref=db.backref("saved_jobs", lazy="dynamic", cascade="all, delete-orphan")
    )
    job = db.relationship(
        "Job", backref=db.backref("saved_by", lazy="dynamic", cascade="all, delete-orphan")
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "job_id", name="uq_user_saved_job"),
    )
