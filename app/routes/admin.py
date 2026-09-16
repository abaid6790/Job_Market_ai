from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import (
    AdminAddCategoryForm,
    AdminAddSkillForm,
    AdminAddAliasForm,
    AdminAssignCategoryForm,
    DataImportForm,
    AdminAddLearningResourceForm,
)
from app.models import SkillCategory, Skill, SkillAlias, UserSkill, LearningResource
from app.services.auth.decorators import admin_required
from app.services.auth.audit import log_event
from app.services.skills.normalizer import normalize_text
from app.services.market.data_import import parse_csv, parse_xlsx, parse_json, import_jobs, ImportParseError
from app.services.ai import get_ai_manager
from app.services.ai.usage import usage_stats
from app.models import AIUsage

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _category_choices():
    return [(c.id, c.name) for c in SkillCategory.query.order_by(SkillCategory.sort_order).all()]


@admin_bp.route("/taxonomy")
@login_required
@admin_required
def taxonomy():
    categories = SkillCategory.query.order_by(SkillCategory.sort_order).all()
    uncategorized = (
        Skill.query.filter_by(category_id=None, is_active=True)
        .order_by(Skill.created_at.desc())
        .all()
    )
    category_form = AdminAddCategoryForm()
    skill_form = AdminAddSkillForm()
    skill_form.category_id.choices = _category_choices()
    assign_form = AdminAssignCategoryForm()
    assign_form.category_id.choices = _category_choices()
    alias_form = AdminAddAliasForm()

    return render_template(
        "admin/taxonomy.html",
        categories=categories,
        uncategorized=uncategorized,
        category_form=category_form,
        skill_form=skill_form,
        assign_form=assign_form,
        alias_form=alias_form,
    )


@admin_bp.route("/taxonomy/categories", methods=["POST"])
@login_required
@admin_required
def add_category():
    form = AdminAddCategoryForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        slug = normalize_text(name).replace(" ", "-")
        if SkillCategory.query.filter_by(name=name).first():
            flash(f'Category "{name}" already exists.', "info")
        else:
            db.session.add(
                SkillCategory(name=name, slug=slug, description=(form.description.data or "").strip() or None)
            )
            db.session.commit()
            flash(f'Category "{name}" added.', "success")
    else:
        for errs in form.errors.values():
            for e in errs:
                flash(e, "danger")
    return redirect(url_for("admin.taxonomy"))


@admin_bp.route("/taxonomy/skills", methods=["POST"])
@login_required
@admin_required
def add_skill():
    form = AdminAddSkillForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        normalized = normalize_text(form.name.data)
        if Skill.query.filter_by(normalized_name=normalized).first():
            flash(f'Skill "{form.name.data}" already exists.', "info")
        else:
            db.session.add(
                Skill(
                    name=form.name.data.strip(),
                    normalized_name=normalized,
                    category_id=form.category_id.data,
                    is_user_suggested=False,
                    is_active=True,
                )
            )
            db.session.commit()
            flash(f'Skill "{form.name.data}" added.', "success")
    else:
        for errs in form.errors.values():
            for e in errs:
                flash(e, "danger")
    return redirect(url_for("admin.taxonomy"))


@admin_bp.route("/taxonomy/skills/<int:skill_id>/assign", methods=["POST"])
@login_required
@admin_required
def assign_category(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    form = AdminAssignCategoryForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        skill.category_id = form.category_id.data
        skill.is_user_suggested = False
        db.session.commit()
        flash(f'"{skill.name}" assigned to a category.', "success")
    else:
        for errs in form.errors.values():
            for e in errs:
                flash(e, "danger")
    return redirect(url_for("admin.taxonomy"))


@admin_bp.route("/taxonomy/skills/<int:skill_id>/alias", methods=["POST"])
@login_required
@admin_required
def add_alias(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    form = AdminAddAliasForm()
    if form.validate_on_submit():
        normalized_alias = normalize_text(form.alias.data)
        if normalized_alias == skill.normalized_name:
            flash("Alias can't be identical to the skill's own name.", "danger")
        elif SkillAlias.query.filter_by(normalized_alias=normalized_alias).first():
            flash("That alias is already mapped to a skill.", "info")
        else:
            db.session.add(
                SkillAlias(skill_id=skill.id, alias=form.alias.data.strip(), normalized_alias=normalized_alias)
            )
            db.session.commit()
            flash(f'Alias "{form.alias.data}" added to "{skill.name}".', "success")
    else:
        for errs in form.errors.values():
            for e in errs:
                flash(e, "danger")
    return redirect(url_for("admin.taxonomy"))


@admin_bp.route("/taxonomy/skills/<int:skill_id>/deactivate", methods=["POST"])
@login_required
@admin_required
def deactivate_skill(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    skill.is_active = False
    db.session.commit()
    flash(f'"{skill.name}" deactivated.', "info")
    return redirect(url_for("admin.taxonomy"))


@admin_bp.route("/data-import", methods=["GET", "POST"])
@login_required
@admin_required
def data_import():
    form = DataImportForm()
    result = None

    if form.validate_on_submit():
        uploaded_file = form.file.data
        filename = uploaded_file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        file_bytes = uploaded_file.read()

        try:
            if ext == "csv":
                rows = parse_csv(file_bytes)
            elif ext == "xlsx":
                rows = parse_xlsx(file_bytes)
            elif ext == "json":
                rows = parse_json(file_bytes)
            else:
                flash("Unsupported file type. Please upload CSV, XLSX, or JSON.", "danger")
                return redirect(url_for("admin.data_import"))

            result = import_jobs(rows, current_user.id)
            flash(
                f"Import complete: {result['imported']} imported, "
                f"{result['duplicates']} duplicates skipped, {result['skipped']} rows skipped.",
                "success",
            )
        except ImportParseError as exc:
            flash(str(exc), "danger")

    return render_template("admin/data_import.html", form=form, result=result)


@admin_bp.route("/ai-status")
@login_required
@admin_required
def ai_status():
    manager = get_ai_manager()
    configured = manager.configured_providers()
    fallback_order = manager._fallback_order()

    provider_details = []
    for name, provider in manager.providers.items():
        detail = {
            "name": name,
            "model": getattr(provider, "model", None),
            "is_default": name == manager.default,
            "in_fallback_order": name in fallback_order,
        }
        if name == "gemini":
            detail["key_status"] = provider.rotator.status()
        provider_details.append(detail)

    recent_usage = AIUsage.query.order_by(AIUsage.created_at.desc()).limit(25).all()

    return render_template(
        "admin/ai_status.html",
        configured=configured,
        provider_details=provider_details,
        fallback_order=fallback_order,
        stats=usage_stats(),
        recent_usage=recent_usage,
    )


@admin_bp.route("/learning-resources", methods=["GET", "POST"])
@login_required
@admin_required
def learning_resources():
    form = AdminAddLearningResourceForm()
    form.skill_id.choices = [(s.id, s.name) for s in Skill.query.filter_by(is_active=True).order_by(Skill.name).all()]

    if form.validate_on_submit():
        existing = LearningResource.query.filter_by(skill_id=form.skill_id.data, url=form.url.data.strip()).first()
        if existing:
            flash("That resource is already listed for this skill.", "info")
        else:
            db.session.add(
                LearningResource(
                    skill_id=form.skill_id.data,
                    title=form.title.data.strip(),
                    url=form.url.data.strip(),
                    resource_type=form.resource_type.data,
                    is_curated=False,
                )
            )
            db.session.commit()
            flash("Learning resource added.", "success")
        return redirect(url_for("admin.learning_resources"))

    resources = LearningResource.query.order_by(LearningResource.skill_id).all()
    return render_template("admin/learning_resources.html", form=form, resources=resources)


@admin_bp.route("/learning-resources/<int:resource_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_learning_resource(resource_id):
    resource = LearningResource.query.get_or_404(resource_id)
    db.session.delete(resource)
    db.session.commit()
    flash("Learning resource removed.", "info")
    return redirect(url_for("admin.learning_resources"))


# ==================================================
# Phase 12 — user management, audit log, system overview
# ==================================================

@admin_bp.route("/users")
@login_required
@admin_required
def users():
    from app.models import User

    query = request.args.get("q", "", type=str).strip()
    users_query = User.query
    if query:
        users_query = users_query.filter(User.email.ilike(f"%{query}%"))
    all_users = users_query.order_by(User.created_at.desc()).limit(200).all()
    return render_template("admin/users.html", users=all_users, query=query)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    from app.models import User

    user = User.query.get_or_404(user_id)

    # An admin disabling themselves would immediately lock themselves out
    # with no way back in through the UI — block it explicitly rather
    # than letting it happen and calling it the admin's fault.
    if user.id == current_user.id:
        flash("You can't disable your own account.", "danger")
        return redirect(url_for("admin.users"))

    user.is_active_account = not user.is_active_account
    db.session.commit()

    action = "user_enabled" if user.is_active_account else "user_disabled"
    log_event("admin", action, description=f"user #{user.id} ({user.email})")
    flash(f"{user.email} {'enabled' if user.is_active_account else 'disabled'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_user_admin(user_id):
    from app.models import User

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You can't change your own admin status.", "danger")
        return redirect(url_for("admin.users"))

    user.is_admin = not user.is_admin
    db.session.commit()

    action = "admin_granted" if user.is_admin else "admin_revoked"
    log_event("admin", action, description=f"user #{user.id} ({user.email})")
    flash(f"Admin rights {'granted to' if user.is_admin else 'revoked from'} {user.email}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/audit-log")
@login_required
@admin_required
def audit_log():
    from app.models import ActivityLog

    category = request.args.get("category", "", type=str).strip()
    query = ActivityLog.query
    if category:
        query = query.filter_by(category=category)
    entries = query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_log.html", entries=entries, category=category)


@admin_bp.route("/overview")
@login_required
@admin_required
def overview():
    from app.models import (
        User, Resume, Job, JobAnalysis, SavedJob, AIConversation,
        CareerRoadmap, ActivityLog, Skill,
    )

    stats = {
        "users_total": User.query.count(),
        "users_verified": User.query.filter_by(is_email_verified=True).count(),
        "users_disabled": User.query.filter_by(is_active_account=False).count(),
        "admins": User.query.filter_by(is_admin=True).count(),
        "resumes": Resume.query.count(),
        "jobs": Job.query.count(),
        "match_reports": JobAnalysis.query.count(),
        "saved_jobs": SavedJob.query.count(),
        "conversations": AIConversation.query.count(),
        "roadmaps": CareerRoadmap.query.count(),
        "skills": Skill.query.count(),
        "user_suggested_skills": Skill.query.filter_by(is_user_suggested=True).count(),
        "audit_entries": ActivityLog.query.count(),
    }
    recent_failed_logins = (
        ActivityLog.query.filter_by(action="login_failed")
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template("admin/overview.html", stats=stats, recent_failed_logins=recent_failed_logins)
