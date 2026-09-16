from flask import Blueprint, render_template, request, abort, jsonify
from flask_login import login_required, current_user

from app.models import Resume, Job
from app.services.auth.decorators import verified_required
from app.services.advanced.skill_graph import build_skill_graph
from app.services.advanced.clustering import cluster_jobs
from app.services.advanced.forecasting import forecast_skill_demand
from app.services.advanced.resume_comparison import compare_resumes

advanced_bp = Blueprint("advanced", __name__, url_prefix="/advanced")


@advanced_bp.route("/")
@login_required
@verified_required
def index():
    return render_template("advanced/index.html")


@advanced_bp.route("/skill-graph")
@login_required
@verified_required
def skill_graph():
    return render_template("advanced/skill_graph.html", graph=build_skill_graph())


@advanced_bp.route("/skill-graph.json")
@login_required
@verified_required
def skill_graph_json():
    return jsonify(build_skill_graph())


@advanced_bp.route("/clusters")
@login_required
@verified_required
def clusters():
    return render_template("advanced/clusters.html", result=cluster_jobs())


@advanced_bp.route("/forecast")
@login_required
@verified_required
def forecast():
    return render_template("advanced/forecast.html", result=forecast_skill_demand())


@advanced_bp.route("/compare-resumes")
@login_required
@verified_required
def compare():
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

    selected_ids = request.args.getlist("resume_id", type=int)
    job_id = request.args.get("job_id", type=int)

    result = None
    job = None
    if selected_ids:
        selected = [r for r in resumes if r.id in selected_ids]
        # Ownership is implicit (resumes is already user-scoped), but be
        # explicit rather than relying on that filter staying in place.
        for r in selected:
            if r.user_id != current_user.id:
                abort(403)

        if job_id:
            candidate = Job.query.filter_by(id=job_id, status="completed").first()
            if candidate and candidate.user_id == current_user.id:
                job = candidate

        result = compare_resumes(current_user, selected, job)

    return render_template(
        "advanced/compare.html",
        resumes=resumes,
        jobs=jobs,
        selected_ids=selected_ids,
        selected_job_id=job_id,
        result=result,
    )
