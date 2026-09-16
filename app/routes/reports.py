from flask import Blueprint, render_template, redirect, url_for, flash, abort, Response, request
from flask_login import login_required, current_user

from app.models import Resume, Job, JobAnalysis, CareerRoadmap
from app.services.auth.decorators import verified_required
from app.services.reports.generator import (
    gather_resume_report,
    gather_match_report,
    gather_skill_gap_report,
    gather_roadmap_report,
    gather_market_report,
)
from app.services.reports.exporters import export, EXPORTERS
from app.services.matching.ats_analysis import compute_ats_analysis
from app.services.resume.improvement import analyze_resume
from app.services.resume.ai_suggestions import get_ai_suggestions
from app.services.ai import get_ai_manager

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _owned_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        abort(403)
    return resume


def _owned_job_analysis(report_id):
    report = JobAnalysis.query.get_or_404(report_id)
    if report.user_id != current_user.id:
        abort(403)
    return report


def _send(data, fmt, filename_stem):
    if fmt not in EXPORTERS:
        abort(404)
    content, mimetype, extension = export(data, fmt)
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.{extension}"'},
    )


@reports_bp.route("/")
@login_required
@verified_required
def index():
    resumes = (
        Resume.query.filter_by(user_id=current_user.id, status="completed")
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    match_reports = (
        JobAnalysis.query.filter_by(user_id=current_user.id)
        .order_by(JobAnalysis.updated_at.desc())
        .all()
    )
    roadmap = CareerRoadmap.query.filter_by(user_id=current_user.id).first()

    return render_template(
        "reports/index.html",
        resumes=resumes,
        match_reports=match_reports,
        roadmap=roadmap,
        formats=list(EXPORTERS.keys()),
    )


@reports_bp.route("/resume/<int:resume_id>.<fmt>")
@login_required
@verified_required
def resume_report(resume_id, fmt):
    resume = _owned_resume(resume_id)
    return _send(gather_resume_report(resume), fmt, f"resume-analysis-{resume.id}")


@reports_bp.route("/match/<int:report_id>.<fmt>")
@login_required
@verified_required
def match_report(report_id, fmt):
    report = _owned_job_analysis(report_id)
    return _send(gather_match_report(report), fmt, f"match-report-{report.id}")


@reports_bp.route("/skill-gaps.<fmt>")
@login_required
@verified_required
def skill_gap_report(fmt):
    return _send(gather_skill_gap_report(current_user), fmt, "skill-gap-report")


@reports_bp.route("/roadmap.<fmt>")
@login_required
@verified_required
def roadmap_report(fmt):
    roadmap = CareerRoadmap.query.filter_by(user_id=current_user.id).first()
    if roadmap is None:
        flash("You don't have a career roadmap yet to export.", "info")
        return redirect(url_for("reports.index"))
    return _send(gather_roadmap_report(roadmap), fmt, "career-roadmap")


@reports_bp.route("/market.<fmt>")
@login_required
@verified_required
def market_report(fmt):
    return _send(gather_market_report(), fmt, "market-analysis")


# --- ATS analysis ---

@reports_bp.route("/ats")
@login_required
@verified_required
def ats_index():
    match_reports = (
        JobAnalysis.query.filter_by(user_id=current_user.id)
        .order_by(JobAnalysis.updated_at.desc())
        .all()
    )
    return render_template("reports/ats_index.html", match_reports=match_reports)


@reports_bp.route("/ats/<int:report_id>")
@login_required
@verified_required
def ats_detail(report_id):
    report = _owned_job_analysis(report_id)
    analysis = compute_ats_analysis(report.resume, report.job)
    return render_template("reports/ats_detail.html", report=report, analysis=analysis)


# --- Resume improvement ---

@reports_bp.route("/improve")
@login_required
@verified_required
def improve_index():
    resumes = (
        Resume.query.filter_by(user_id=current_user.id, status="completed")
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    jobs = (
        Job.query.filter_by(user_id=current_user.id, status="completed")
        .order_by(Job.created_at.desc())
        .all()
    )
    return render_template("reports/improve_index.html", resumes=resumes, jobs=jobs)


@reports_bp.route("/improve/<int:resume_id>")
@login_required
@verified_required
def improve_detail(resume_id):
    resume = _owned_resume(resume_id)

    job = None
    job_id = request.args.get("job_id", type=int)
    if job_id:
        candidate = Job.query.filter_by(id=job_id, status="completed").first()
        if candidate and candidate.user_id == current_user.id:
            job = candidate

    analysis = analyze_resume(resume, job)
    manager = get_ai_manager()

    return render_template(
        "reports/improve_detail.html",
        resume=resume,
        job=job,
        analysis=analysis,
        provider_available=bool(manager.configured_providers()),
    )


@reports_bp.route("/improve/<int:resume_id>/ai", methods=["POST"])
@login_required
@verified_required
def improve_ai(resume_id):
    resume = _owned_resume(resume_id)

    job = None
    job_id = request.form.get("job_id", type=int)
    if job_id:
        candidate = Job.query.filter_by(id=job_id, status="completed").first()
        if candidate and candidate.user_id == current_user.id:
            job = candidate

    analysis = analyze_resume(resume, job)
    ai_result = get_ai_suggestions(current_user, resume, analysis, job)
    manager = get_ai_manager()

    return render_template(
        "reports/improve_detail.html",
        resume=resume,
        job=job,
        analysis=analysis,
        ai_result=ai_result,
        provider_available=bool(manager.configured_providers()),
    )
