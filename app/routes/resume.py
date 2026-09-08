from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    current_app,
    send_from_directory,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.forms import ResumeUploadForm
from app.models import Resume, ResumeSection, ResumeExperience, ResumeEducation, ResumeSkill
from app.services.auth.decorators import verified_required
from app.services.resume.storage import save_resume_file, delete_resume_file, FileValidationError
from app.services.resume.pipeline import process_resume

resume_bp = Blueprint("resume", __name__, url_prefix="/resume")


@resume_bp.route("/")
@login_required
@verified_required
def index():
    form = ResumeUploadForm()
    resumes = (
        Resume.query.filter_by(user_id=current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    return render_template("resume/index.html", form=form, resumes=resumes)


@resume_bp.route("/upload", methods=["POST"])
@login_required
@verified_required
def upload():
    form = ResumeUploadForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("resume.index"))

    uploaded_file = form.file.data
    original_filename = secure_filename(uploaded_file.filename) or "resume"
    file_bytes = uploaded_file.read()

    try:
        storage_info = save_resume_file(
            current_app.config["UPLOAD_FOLDER"], current_user.id, original_filename, file_bytes
        )
    except FileValidationError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("resume.index"))

    is_first_resume = Resume.query.filter_by(user_id=current_user.id).count() == 0

    resume = Resume(
        user_id=current_user.id,
        original_filename=original_filename,
        stored_filename=storage_info["stored_filename"],
        file_type=storage_info["file_type"],
        file_size_bytes=storage_info["file_size_bytes"],
        status="pending",
        is_primary=is_first_resume,
    )
    db.session.add(resume)
    db.session.commit()

    process_resume(resume, storage_info["file_path"])

    if resume.status == "completed":
        flash("Resume uploaded and parsed successfully.", "success")
    else:
        flash(
            f"Resume uploaded, but parsing failed: {resume.error_message}",
            "warning",
        )

    return redirect(url_for("resume.detail", resume_id=resume.id))


def _get_owned_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        abort(403)
    return resume


@resume_bp.route("/<int:resume_id>")
@login_required
@verified_required
def detail(resume_id):
    resume = _get_owned_resume(resume_id)
    experiences = resume.experiences.all()
    education_entries = resume.education_entries.all()
    resume_skills = resume.resume_skills.all()
    sections = resume.sections.all()
    return render_template(
        "resume/detail.html",
        resume=resume,
        experiences=experiences,
        education_entries=education_entries,
        resume_skills=resume_skills,
        sections=sections,
    )


@resume_bp.route("/<int:resume_id>/download")
@login_required
@verified_required
def download(resume_id):
    resume = _get_owned_resume(resume_id)
    user_dir = f"user_{resume.user_id}"
    directory = current_app.config["UPLOAD_FOLDER"] + "/" + user_dir
    return send_from_directory(
        directory, resume.stored_filename, as_attachment=True, download_name=resume.original_filename
    )


@resume_bp.route("/<int:resume_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete(resume_id):
    resume = _get_owned_resume(resume_id)
    user_dir = f"user_{resume.user_id}"
    file_path = f"{current_app.config['UPLOAD_FOLDER']}/{user_dir}/{resume.stored_filename}"
    delete_resume_file(file_path)

    was_primary = resume.is_primary
    db.session.delete(resume)
    db.session.commit()

    if was_primary:
        next_resume = (
            Resume.query.filter_by(user_id=current_user.id)
            .order_by(Resume.uploaded_at.desc())
            .first()
        )
        if next_resume:
            next_resume.is_primary = True
            db.session.commit()

    flash("Resume deleted.", "info")
    return redirect(url_for("resume.index"))


@resume_bp.route("/<int:resume_id>/set-primary", methods=["POST"])
@login_required
@verified_required
def set_primary(resume_id):
    resume = _get_owned_resume(resume_id)
    Resume.query.filter_by(user_id=current_user.id, is_primary=True).update({"is_primary": False})
    resume.is_primary = True
    db.session.commit()
    flash(f'"{resume.original_filename}" set as your primary resume.', "success")
    return redirect(url_for("resume.index"))


@resume_bp.route("/<int:resume_id>/reprocess", methods=["POST"])
@login_required
@verified_required
def reprocess(resume_id):
    resume = _get_owned_resume(resume_id)
    user_dir = f"user_{resume.user_id}"
    file_path = f"{current_app.config['UPLOAD_FOLDER']}/{user_dir}/{resume.stored_filename}"

    # Clear previously derived rows before re-parsing. Bulk-delete via
    # explicit queries rather than the ordered dynamic relationships
    # (resume.sections etc.) — SQLAlchemy refuses Query.delete() on a
    # relationship that has order_by() applied.
    ResumeSection.query.filter_by(resume_id=resume.id).delete()
    ResumeExperience.query.filter_by(resume_id=resume.id).delete()
    ResumeEducation.query.filter_by(resume_id=resume.id).delete()
    ResumeSkill.query.filter_by(resume_id=resume.id).delete()
    db.session.commit()

    process_resume(resume, file_path)
    flash("Resume re-processed.", "info")
    return redirect(url_for("resume.detail", resume_id=resume.id))
