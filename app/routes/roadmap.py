from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import UpdateRoadmapSkillForm
from app.models import CareerRoadmap, RoadmapSkill, Recommendation
from app.services.auth.decorators import verified_required
from app.services.roadmap.roadmap_generator import generate_roadmap
from app.services.roadmap.project_recommender import generate_project_recommendations
from app.services.roadmap.learning_resources import get_resources_for_skill

roadmap_bp = Blueprint("roadmap", __name__, url_prefix="/roadmap")


@roadmap_bp.route("/")
@login_required
@verified_required
def index():
    roadmap = CareerRoadmap.query.filter_by(user_id=current_user.id).first()
    roadmap_skills = []
    if roadmap:
        for rs in roadmap.roadmap_skills.all():
            roadmap_skills.append(
                {
                    "roadmap_skill": rs,
                    "resources": get_resources_for_skill(rs.skill_id),
                    "form": UpdateRoadmapSkillForm(status=rs.status),
                }
            )

    recommendations = (
        Recommendation.query.filter_by(user_id=current_user.id, recommendation_type="project")
        .order_by(Recommendation.created_at.desc())
        .all()
    )

    return render_template(
        "roadmap/index.html",
        roadmap=roadmap,
        roadmap_skills=roadmap_skills,
        recommendations=recommendations,
    )


@roadmap_bp.route("/generate", methods=["POST"])
@login_required
@verified_required
def generate():
    roadmap = generate_roadmap(current_user)
    if roadmap is None:
        flash(
            "Not enough data to build a roadmap yet — run at least one resume-job "
            "match first so we know which skills you're actually missing.",
            "info",
        )
    else:
        flash("Career roadmap generated from your skill gaps.", "success")
    return redirect(url_for("roadmap.index"))


@roadmap_bp.route("/skills/<int:roadmap_skill_id>/status", methods=["POST"])
@login_required
@verified_required
def update_skill_status(roadmap_skill_id):
    rs = RoadmapSkill.query.get_or_404(roadmap_skill_id)
    if rs.roadmap.user_id != current_user.id:
        abort(403)

    form = UpdateRoadmapSkillForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("roadmap.index"))

    rs.status = form.status.data
    db.session.commit()
    flash(f'"{rs.skill.name}" marked as {rs.status.replace("_", " ")}.', "success")
    return redirect(url_for("roadmap.index"))


@roadmap_bp.route("/recommendations/generate", methods=["POST"])
@login_required
@verified_required
def generate_recommendations():
    recs = generate_project_recommendations(current_user)
    if not recs:
        flash(
            "Not enough data for project recommendations yet — run at least one "
            "resume-job match first.",
            "info",
        )
    else:
        flash(f"Generated {len(recs)} project recommendation(s).", "success")
    return redirect(url_for("roadmap.index"))


@roadmap_bp.route("/recommendations/<int:recommendation_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete_recommendation(recommendation_id):
    rec = Recommendation.query.get_or_404(recommendation_id)
    if rec.user_id != current_user.id:
        abort(403)
    db.session.delete(rec)
    db.session.commit()
    flash("Recommendation removed.", "info")
    return redirect(url_for("roadmap.index"))
