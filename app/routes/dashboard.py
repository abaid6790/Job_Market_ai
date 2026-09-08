from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import UserSkill, UserCertification, Resume
from app.services.auth.decorators import verified_required

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
@verified_required
def index():
    skill_count = UserSkill.query.filter_by(user_id=current_user.id).count()
    cert_count = UserCertification.query.filter_by(user_id=current_user.id).count()
    profile = current_user.profile
    primary_resume = Resume.query.filter_by(user_id=current_user.id, is_primary=True).first()
    return render_template(
        "dashboard/index.html",
        user=current_user,
        profile=profile,
        skill_count=skill_count,
        cert_count=cert_count,
        primary_resume=primary_resume,
    )
