from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import MatchAnalyzeForm, QuickMatchForm
from app.models import Resume, Job, JobAnalysis, UserSkill
from app.services.auth.decorators import verified_required
from app.services.matching.engine import save_match_report

matching_bp = Blueprint("matching", __name__, url_prefix="/match")


def _user_resume_choices():
    resumes = (
        Resume.query.filter_by(user_id=current_user.id, status="completed")
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    return [(r.id, r.original_filename) for r in resumes]


def _user_job_choices():
    jobs = (
        Job.query.filter_by(user_id=current_user.id, status="completed")
        .order_by(Job.created_at.desc())
        .all()
    )
    return [(j.id, j.title or f"Job #{j.id}") for j in jobs]


@matching_bp.route("/", methods=["GET"])
@login_required
@verified_required
def index():
    form = MatchAnalyzeForm()
    form.resume_id.choices = _user_resume_choices()
    form.job_id.choices = _user_job_choices()

    preselect_resume_id = request.args.get("resume_id", type=int)
    preselect_job_id = request.args.get("job_id", type=int)
    if preselect_resume_id:
        form.resume_id.data = preselect_resume_id
    if preselect_job_id:
        form.job_id.data = preselect_job_id

    reports = (
        JobAnalysis.query.filter_by(user_id=current_user.id)
        .order_by(JobAnalysis.updated_at.desc())
        .all()
    )

    return render_template(
        "matching/index.html",
        form=form,
        reports=reports,
        has_resumes=bool(form.resume_id.choices),
        has_jobs=bool(form.job_id.choices),
    )


@matching_bp.route("/analyze", methods=["POST"])
@login_required
@verified_required
def analyze():
    form = MatchAnalyzeForm()
    form.resume_id.choices = _user_resume_choices()
    form.job_id.choices = _user_job_choices()

    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("matching.index"))

    resume = Resume.query.get_or_404(form.resume_id.data)
    job = Job.query.get_or_404(form.job_id.data)
    if resume.user_id != current_user.id or job.user_id != current_user.id:
        abort(403)

    report = save_match_report(current_user, resume, job)
    flash("Match analysis complete.", "success")
    return redirect(url_for("matching.detail", report_id=report.id))


def _get_owned_report(report_id):
    report = JobAnalysis.query.get_or_404(report_id)
    if report.user_id != current_user.id:
        abort(403)
    return report


@matching_bp.route("/<int:report_id>")
@login_required
@verified_required
def detail(report_id):
    report = _get_owned_report(report_id)

    critical = report.skill_gaps.filter_by(gap_category="critical").all()
    important = report.skill_gaps.filter_by(gap_category="important").all()
    optional = report.skill_gaps.filter_by(gap_category="optional").all()

    user_skill_ids = {us.skill_id for us in UserSkill.query.filter_by(user_id=current_user.id).all()}
    matched_required = [
        js for js in report.job.job_skills.filter_by(requirement_level="required").all()
        if js.skill_id in user_skill_ids
    ]
    matched_preferred = [
        js for js in report.job.job_skills.filter_by(requirement_level="preferred").all()
        if js.skill_id in user_skill_ids
    ]

    return render_template(
        "matching/detail.html",
        report=report,
        critical=critical,
        important=important,
        optional=optional,
        matched_required=matched_required,
        matched_preferred=matched_preferred,
    )


@matching_bp.route("/quick/<int:job_id>", methods=["POST"])
@login_required
@verified_required
def quick_match(job_id):
    """Match the current user's own resume against ANY completed job in
    the shared pool (not just one they personally analyzed) — used from
    job search / saved job pages. Resume ownership is still strictly
    enforced; job ownership is not, since job posting content is shared
    market data (consistent with Phase 5's aggregates), unlike the
    private resume."""
    job = Job.query.filter_by(id=job_id, status="completed").first_or_404()

    form = QuickMatchForm()
    form.resume_id.choices = _user_resume_choices()

    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(request.referrer or url_for("job.browse_detail", job_id=job.id))

    resume = Resume.query.get_or_404(form.resume_id.data)
    if resume.user_id != current_user.id:
        abort(403)

    report = save_match_report(current_user, resume, job)
    flash("Match analysis complete.", "success")
    return redirect(url_for("matching.detail", report_id=report.id))


@matching_bp.route("/<int:report_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete(report_id):
    report = _get_owned_report(report_id)
    db.session.delete(report)
    db.session.commit()
    flash("Match analysis deleted.", "info")
    return redirect(url_for("matching.index"))
