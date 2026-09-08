import os
import tempfile

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.forms import JobAnalyzeForm, JobSearchForm, SaveJobForm
from app.models import Job, JobSection, JobSkill, Resume
from app.services.auth.decorators import verified_required
from app.services.resume.storage import (
    validate_extension,
    validate_signature,
    FileValidationError,
)
from app.services.resume.extractor import extract_text, ExtractionError
from app.services.job.pipeline import process_job
from app.services.job.search import search_jobs

job_bp = Blueprint("job", __name__, url_prefix="/jobs")


def _extract_text_from_upload(uploaded_file) -> tuple[str, str]:
    """Validate + extract text from an uploaded job description file.

    Uses a throwaway temp file only for extraction — unlike resumes, job
    postings aren't offered for re-download, so nothing is persisted to
    the permanent uploads directory.
    """
    original_filename = secure_filename(uploaded_file.filename) or "job_description"
    file_bytes = uploaded_file.read()

    if len(file_bytes) == 0:
        raise FileValidationError("The uploaded file is empty.")

    ext = validate_extension(original_filename)
    validate_signature(file_bytes, ext)

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        text = extract_text(tmp_path, ext)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return text, original_filename


@job_bp.route("/")
@login_required
@verified_required
def index():
    form = JobAnalyzeForm()
    jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.created_at.desc()).all()
    return render_template("jobs/index.html", form=form, jobs=jobs)


@job_bp.route("/analyze", methods=["POST"])
@login_required
@verified_required
def analyze():
    form = JobAnalyzeForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("job.index"))

    original_filename = None
    if form.file.data:
        try:
            raw_text, original_filename = _extract_text_from_upload(form.file.data)
        except (FileValidationError, ExtractionError) as exc:
            flash(str(exc), "danger")
            return redirect(url_for("job.index"))
        source = "uploaded"
    else:
        raw_text = form.job_text.data
        source = "pasted"

    job = Job(
        user_id=current_user.id,
        source=source,
        original_filename=original_filename,
        status="pending",
    )
    db.session.add(job)
    db.session.commit()

    process_job(job, raw_text)

    if job.status == "completed":
        flash("Job description analyzed successfully.", "success")
    else:
        flash(f"Analysis failed: {job.error_message}", "warning")

    return redirect(url_for("job.detail", job_id=job.id))


def _get_owned_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)
    return job


@job_bp.route("/<int:job_id>")
@login_required
@verified_required
def detail(job_id):
    job = _get_owned_job(job_id)
    required_skills = job.job_skills.filter_by(requirement_level="required").all()
    preferred_skills = job.job_skills.filter_by(requirement_level="preferred").all()
    sections = job.sections.all()
    return render_template(
        "jobs/detail.html",
        job=job,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        sections=sections,
    )


@job_bp.route("/<int:job_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete(job_id):
    job = _get_owned_job(job_id)
    db.session.delete(job)
    db.session.commit()
    flash("Job analysis deleted.", "info")
    return redirect(url_for("job.index"))


@job_bp.route("/<int:job_id>/reprocess", methods=["POST"])
@login_required
@verified_required
def reprocess(job_id):
    job = _get_owned_job(job_id)
    if not job.raw_text:
        flash("Can't reprocess: original text is unavailable.", "danger")
        return redirect(url_for("job.detail", job_id=job.id))

    # Bulk-delete via explicit queries — job.sections has order_by() applied,
    # and SQLAlchemy refuses Query.delete() on an ordered relationship.
    JobSection.query.filter_by(job_id=job.id).delete()
    JobSkill.query.filter_by(job_id=job.id).delete()
    db.session.commit()

    process_job(job, job.raw_text)
    flash("Job re-processed.", "info")
    return redirect(url_for("job.detail", job_id=job.id))


@job_bp.route("/search")
@login_required
@verified_required
def search():
    form = JobSearchForm(request.args, meta={"csrf": False})
    page = request.args.get("page", 1, type=int)

    results = search_jobs(
        query=form.query.data or None,
        location=form.location.data or None,
        remote_status=form.remote_status.data or None,
        employment_type=form.employment_type.data or None,
        max_experience=int(form.max_experience.data) if form.max_experience.data else None,
        min_salary=int(form.min_salary.data) if form.min_salary.data else None,
        page=page,
    )

    saved_job_ids = set()
    if current_user.is_authenticated:
        from app.models import SavedJob

        saved_job_ids = {
            sj.job_id for sj in SavedJob.query.filter_by(user_id=current_user.id).all()
        }

    return render_template(
        "jobs/search.html", form=form, results=results, saved_job_ids=saved_job_ids
    )


@job_bp.route("/search/<int:job_id>")
@login_required
@verified_required
def browse_detail(job_id):
    """Read-only view of any completed job in the shared pool — unlike
    `detail()` above, this is NOT ownership-gated, since job posting
    content isn't private (consistent with Phase 5's market aggregates).
    Only the owner's private analyses page offers edit/delete/reprocess."""
    job = Job.query.filter_by(id=job_id, status="completed").first_or_404()

    from app.models import SavedJob

    required_skills = job.job_skills.filter_by(requirement_level="required").all()
    preferred_skills = job.job_skills.filter_by(requirement_level="preferred").all()
    already_saved = (
        SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first() is not None
    )

    resumes = (
        current_user.resumes.filter_by(status="completed").order_by(Resume.uploaded_at.desc()).all()
    )

    return render_template(
        "jobs/browse_detail.html",
        job=job,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        already_saved=already_saved,
        has_resumes=bool(resumes),
    )


@job_bp.route("/search/<int:job_id>/save", methods=["POST"])
@login_required
@verified_required
def save(job_id):
    job = Job.query.filter_by(id=job_id, status="completed").first_or_404()

    from app.models import SavedJob

    existing = SavedJob.query.filter_by(user_id=current_user.id, job_id=job.id).first()
    if existing:
        flash("You've already saved this job.", "info")
    else:
        db.session.add(SavedJob(user_id=current_user.id, job_id=job.id))
        db.session.commit()
        flash("Job saved.", "success")

    return redirect(request.referrer or url_for("job.browse_detail", job_id=job.id))
