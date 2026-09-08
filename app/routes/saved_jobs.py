from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import UpdateSavedJobForm
from app.models import SavedJob
from app.services.auth.decorators import verified_required

saved_jobs_bp = Blueprint("saved_jobs", __name__, url_prefix="/saved-jobs")


def _get_owned_saved_job(saved_job_id):
    saved_job = SavedJob.query.get_or_404(saved_job_id)
    if saved_job.user_id != current_user.id:
        abort(403)
    return saved_job


@saved_jobs_bp.route("/")
@login_required
@verified_required
def index():
    status_filter = request.args.get("status")
    query = SavedJob.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    saved_jobs = query.order_by(SavedJob.updated_at.desc()).all()

    forms = {}
    for sj in saved_jobs:
        form = UpdateSavedJobForm()
        form.status.data = sj.status
        form.notes.data = sj.notes
        form.application_date.data = sj.application_date.isoformat() if sj.application_date else ""
        form.interview_date.data = sj.interview_date.isoformat() if sj.interview_date else ""
        forms[sj.id] = form

    return render_template(
        "saved_jobs/index.html",
        saved_jobs=saved_jobs,
        forms=forms,
        status_filter=status_filter,
    )


@saved_jobs_bp.route("/tracker")
@login_required
@verified_required
def tracker():
    all_saved = SavedJob.query.filter_by(user_id=current_user.id).all()

    counts = {status: 0 for status in ("saved", "applied", "interview", "offer", "rejected")}
    for sj in all_saved:
        counts[sj.status] = counts.get(sj.status, 0) + 1

    applications = counts["applied"] + counts["interview"] + counts["offer"] + counts["rejected"]
    interview_rate = round((counts["interview"] + counts["offer"]) / applications * 100, 1) if applications else None
    offer_rate = round(counts["offer"] / applications * 100, 1) if applications else None

    application_stage_jobs = [sj for sj in all_saved if sj.status != "saved"]
    application_stage_jobs.sort(key=lambda sj: sj.updated_at, reverse=True)

    return render_template(
        "saved_jobs/tracker.html",
        counts=counts,
        applications=applications,
        interview_rate=interview_rate,
        offer_rate=offer_rate,
        application_stage_jobs=application_stage_jobs,
    )


@saved_jobs_bp.route("/<int:saved_job_id>/update", methods=["POST"])
@login_required
@verified_required
def update(saved_job_id):
    saved_job = _get_owned_saved_job(saved_job_id)
    form = UpdateSavedJobForm()

    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("saved_jobs.index"))

    saved_job.status = form.status.data
    saved_job.notes = form.notes.data.strip() if form.notes.data else None
    saved_job.application_date = (
        datetime.strptime(form.application_date.data.strip(), "%Y-%m-%d").date()
        if form.application_date.data
        else None
    )
    saved_job.interview_date = (
        datetime.strptime(form.interview_date.data.strip(), "%Y-%m-%d").date()
        if form.interview_date.data
        else None
    )
    db.session.commit()
    flash("Saved job updated.", "success")
    return redirect(request.referrer or url_for("saved_jobs.index"))


@saved_jobs_bp.route("/<int:saved_job_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete(saved_job_id):
    saved_job = _get_owned_saved_job(saved_job_id)
    db.session.delete(saved_job)
    db.session.commit()
    flash("Removed from saved jobs.", "info")
    return redirect(url_for("saved_jobs.index"))
