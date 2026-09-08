from functools import wraps

from flask import flash, redirect, url_for, abort
from flask_login import current_user


def verified_required(view_func):
    """Require the user to be logged in AND have a verified email.

    Use in addition to (or instead of) @login_required for any route that
    is a "protected application feature" per the spec.
    """

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_email_verified:
            flash("Please verify your email address to continue.", "warning")
            return redirect(url_for("auth.verify_notice"))
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func):
    """Require the user to be logged in AND flagged as an admin."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped
