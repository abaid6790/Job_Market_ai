from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import Skill
from app.services.auth.decorators import verified_required
from app.services.market import analytics
from app.forms import RoleSearchForm

market_bp = Blueprint("market", __name__, url_prefix="/market")

MIN_JOBS_FOR_DASHBOARD = 1


@market_bp.route("/")
@login_required
@verified_required
def dashboard():
    total = analytics.total_jobs_analyzed()
    if total < MIN_JOBS_FOR_DASHBOARD:
        return render_template("market/dashboard.html", total_jobs=0, has_data=False)

    return render_template(
        "market/dashboard.html",
        has_data=True,
        total_jobs=total,
        skill_demand=analytics.skill_demand(limit=15),
        cooccurrence=analytics.skill_cooccurrence(limit=10),
        trends=analytics.skill_trends(),
        top_titles=analytics.top_titles(limit=10),
        locations=analytics.location_distribution(limit=10),
        remote_dist=analytics.remote_distribution(),
        employment_dist=analytics.employment_type_distribution(),
        education_dist=analytics.education_distribution(),
        experience_dist=analytics.experience_distribution(),
        salary=analytics.salary_stats(),
    )


@market_bp.route("/skills")
@login_required
@verified_required
def skills():
    category_id = request.args.get("category_id", type=int)
    demand = analytics.skill_demand(limit=200)
    if category_id:
        demand = [d for d in demand if d["skill"].category_id == category_id]

    from app.models import SkillCategory

    categories = SkillCategory.query.order_by(SkillCategory.sort_order).all()
    return render_template(
        "market/skills.html",
        demand=demand,
        categories=categories,
        selected_category_id=category_id,
        total_jobs=analytics.total_jobs_analyzed(),
    )


@market_bp.route("/skills/<int:skill_id>")
@login_required
@verified_required
def skill_detail(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    all_demand = analytics.skill_demand(limit=500)
    this_skill_stats = next((d for d in all_demand if d["skill"].id == skill_id), None)

    cooccurring = [
        pair
        for pair in analytics.skill_cooccurrence(limit=500)
        if pair["skill_a"].id == skill_id or pair["skill_b"].id == skill_id
    ][:10]

    return render_template(
        "market/skill_detail.html",
        skill=skill,
        stats=this_skill_stats,
        cooccurring=cooccurring,
        total_jobs=analytics.total_jobs_analyzed(),
    )


@market_bp.route("/roles", methods=["GET", "POST"])
@login_required
@verified_required
def roles():
    form = RoleSearchForm()
    top_titles = analytics.top_titles(limit=20)
    result = None

    query = request.args.get("title") or (form.title.data if form.validate_on_submit() else None)
    if query:
        result = analytics.role_analytics(query)

    return render_template("market/roles.html", form=form, top_titles=top_titles, result=result, query=query)
