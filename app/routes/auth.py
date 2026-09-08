import logging
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)

from app.extensions import db, limiter
from app.forms import (
    RegisterForm,
    LoginForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    ChangePasswordForm,
    ResendVerificationForm,
    DeleteAccountForm,
)
from app.models import User, EmailVerificationToken, PasswordResetToken
from app.services.email.mailer import send_verification_email, send_password_reset_email

logger = logging.getLogger("jobmarket_ai.auth")

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Generic message used for both "email not found" and "email found" cases
# on forgot-password / resend-verification, so we don't leak which emails
# are registered (user enumeration protection).
GENERIC_EMAIL_SENT_MSG = (
    "If an account with that email exists, we've sent instructions to it."
)


def _issue_verification_email(user: User) -> None:
    token = EmailVerificationToken.create_for_user(
        user, current_app.config["EMAIL_TOKEN_EXPIRY_HOURS"]
    )
    db.session.commit()
    verify_url = url_for("auth.verify_email", token=token.token, _external=True)
    send_verification_email(user.email, user.name, verify_url)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing = User.query.filter_by(email=email).first()
        if existing:
            # Don't reveal whether the account exists or not.
            flash(
                "If that email isn't already registered, check your inbox to "
                "finish creating your account.",
                "info",
            )
            return redirect(url_for("auth.login"))

        user = User(email=email, name=form.name.data.strip())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        _issue_verification_email(user)
        logger.info("New registration: %s", email)

        flash(
            "Account created! Check your email for a verification link.",
            "success",
        )
        return redirect(url_for("auth.verify_notice"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify-notice")
def verify_notice():
    return render_template("auth/verify_notice.html")


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    record = EmailVerificationToken.query.filter_by(token=token).first()

    if not record or not record.is_valid:
        flash("That verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.verify_notice"))

    user = record.user
    user.is_email_verified = True
    record.used = True
    db.session.commit()

    flash("Your email has been verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def resend_verification():
    form = ResendVerificationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and not user.is_email_verified:
            _issue_verification_email(user)
        flash(GENERIC_EMAIL_SENT_MSG, "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/resend_verification.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active_account:
            flash("This account has been disabled. Contact support.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        if not user.is_email_verified:
            flash("Please verify your email to unlock all features.", "warning")
            return redirect(url_for("auth.verify_notice"))

        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = PasswordResetToken.create_for_user(
                user, current_app.config["PASSWORD_RESET_EXPIRY_MINUTES"]
            )
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token.token, _external=True)
            send_password_reset_email(user.email, user.name, reset_url)
        flash(GENERIC_EMAIL_SENT_MSG, "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    record = PasswordResetToken.query.filter_by(token=token).first()
    if not record or not record.is_valid:
        flash("That password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = record.user
        user.set_password(form.password.data)
        record.used = True
        # Invalidate any other outstanding reset tokens for this user.
        for other in user.reset_tokens.filter_by(used=False):
            other.used = True
        db.session.commit()
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Your current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Your password has been changed.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.password.data):
            flash("Incorrect password.", "danger")
            return render_template("auth/delete_account.html", form=form)
        # current_user is a LocalProxy that re-resolves on every access, so
        # unwrap the real model instance before logout_user() clears it.
        user = current_user._get_current_object()
        logout_user()
        db.session.delete(user)
        db.session.commit()
        flash("Your account and all associated data have been deleted.", "info")
        return redirect(url_for("main.index"))
    return render_template("auth/delete_account.html", form=form)
