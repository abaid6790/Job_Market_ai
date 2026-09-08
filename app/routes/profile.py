from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import ProfileForm, AddSkillForm, AddCertificationForm
from app.models import UserProfile, UserSkill, UserCertification
from app.services.auth.decorators import verified_required
from app.services.skills.normalizer import get_or_suggest_skill

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


def _get_or_create_profile(user):
    if user.profile:
        return user.profile
    profile = UserProfile(user_id=user.id)
    db.session.add(profile)
    db.session.flush()
    return profile


@profile_bp.route("/", methods=["GET", "POST"])
@login_required
@verified_required
def index():
    profile = _get_or_create_profile(current_user)

    form = ProfileForm(obj=profile)
    if form.validate_on_submit():
        profile.location = (form.location.data or "").strip() or None
        profile.current_role = (form.current_role.data or "").strip() or None
        profile.target_role = (form.target_role.data or "").strip() or None
        profile.years_experience = (
            int(form.years_experience.data) if form.years_experience.data else None
        )
        profile.education_level = form.education_level.data or None
        profile.remote_preference = form.remote_preference.data or None
        profile.bio = (form.bio.data or "").strip() or None
        profile.preferred_industries = (form.preferred_industries.data or "").split(",")
        profile.preferred_locations = (form.preferred_locations.data or "").split(",")
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.index"))
    elif not form.is_submitted():
        # Pre-fill the comma-separated fields on GET (obj= doesn't handle
        # the JSON-backed properties automatically).
        form.preferred_industries.data = ", ".join(profile.preferred_industries)
        form.preferred_locations.data = ", ".join(profile.preferred_locations)

    skill_form = AddSkillForm()
    cert_form = AddCertificationForm()
    user_skills = (
        UserSkill.query.filter_by(user_id=current_user.id)
        .join(UserSkill.skill)
        .order_by(UserSkill.created_at.desc())
        .all()
    )
    certifications = (
        UserCertification.query.filter_by(user_id=current_user.id)
        .order_by(UserCertification.created_at.desc())
        .all()
    )

    return render_template(
        "profile/index.html",
        form=form,
        skill_form=skill_form,
        cert_form=cert_form,
        user_skills=user_skills,
        certifications=certifications,
    )


@profile_bp.route("/skills", methods=["POST"])
@login_required
@verified_required
def add_skill():
    form = AddSkillForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("profile.index"))

    skill = get_or_suggest_skill(form.skill_name.data)

    existing_link = UserSkill.query.filter_by(
        user_id=current_user.id, skill_id=skill.id
    ).first()
    if existing_link:
        flash(f'"{skill.name}" is already on your profile.', "info")
        db.session.rollback()
        return redirect(url_for("profile.index"))

    link = UserSkill(
        user_id=current_user.id,
        skill_id=skill.id,
        proficiency=form.proficiency.data or None,
        years_experience=int(form.years_experience.data) if form.years_experience.data else None,
        source="manual",
    )
    db.session.add(link)
    db.session.commit()
    flash(f'Added "{skill.name}" to your skills.', "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/skills/<int:user_skill_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete_skill(user_skill_id):
    link = UserSkill.query.get_or_404(user_skill_id)
    if link.user_id != current_user.id:
        abort(403)
    db.session.delete(link)
    db.session.commit()
    flash("Skill removed.", "info")
    return redirect(url_for("profile.index"))


@profile_bp.route("/certifications", methods=["POST"])
@login_required
@verified_required
def add_certification():
    form = AddCertificationForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("profile.index"))

    cert = UserCertification(
        user_id=current_user.id,
        name=form.name.data.strip(),
        issuing_organization=(form.issuing_organization.data or "").strip() or None,
        year_obtained=int(form.year_obtained.data) if form.year_obtained.data else None,
    )
    db.session.add(cert)
    db.session.commit()
    flash("Certification added.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/certifications/<int:cert_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete_certification(cert_id):
    cert = UserCertification.query.get_or_404(cert_id)
    if cert.user_id != current_user.id:
        abort(403)
    db.session.delete(cert)
    db.session.commit()
    flash("Certification removed.", "info")
    return redirect(url_for("profile.index"))
