import logging
import os

from flask import Flask, render_template, redirect, url_for, flash, request

from config import config_by_name
from app.extensions import db, login_manager, csrf, limiter, migrate


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    _configure_logging(app)

    # --- Extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    # --- AI provider manager (Phase 7) ---
    from app.services.ai.manager import AIProviderManager

    app.extensions["ai_manager"] = AIProviderManager(app.config)

    # --- User loader for Flask-Login ---
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.profile import profile_bp
    from app.routes.api import api_bp
    from app.routes.admin import admin_bp
    from app.routes.resume import resume_bp
    from app.routes.job import job_bp
    from app.routes.market import market_bp
    from app.routes.matching import matching_bp
    from app.routes.saved_jobs import saved_jobs_bp
    from app.routes.assistant import assistant_bp
    from app.routes.roadmap import roadmap_bp
    from app.routes.reports import reports_bp
    from app.routes.advanced import advanced_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(matching_bp)
    app.register_blueprint(saved_jobs_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(roadmap_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(advanced_bp)


    # --- Security headers (Phase 12) ---
    @app.after_request
    def set_security_headers(response):
        # Defense-in-depth headers. CSP allows the CDNs this app actually
        # uses (Bootstrap, Chart.js) plus 'unsafe-inline' for the small
        # inline scripts/styles in templates — tightening that further
        # would require moving every inline block to a static file, which
        # is a worthwhile follow-up but not a silent change to make here.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'",
        )
        if not app.config.get("DEBUG"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    # --- Error handlers ---
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        app.logger.exception("Unhandled server error")
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def rate_limited(_e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(413)
    def file_too_large(_e):
        flash("That file is too large (max 10 MB).", "danger")
        return redirect(request.referrer or url_for("main.index")), 413

    # --- Template context ---
    @app.context_processor
    def inject_globals():
        return {"app_name": "JobMarket AI"}

    # --- CLI commands ---
    @app.cli.command("seed-taxonomy")
    def seed_taxonomy_command():
        """Load/refresh the built-in skill taxonomy (categories, skills, aliases)."""
        from app.services.skills.seed import seed_taxonomy

        stats = seed_taxonomy()
        print(
            f"Taxonomy seeded: +{stats['categories_added']} categories, "
            f"+{stats['skills_added']} skills, +{stats['aliases_added']} aliases."
        )

    # --- DB bootstrap for dev/test (Phase 14: migrations now manage schema
    # in production — see migrations/ and docs/DEPLOYMENT.md. This convenience
    # create_all() is skipped when running `flask db ...` so Alembic's
    # autogenerate can see a true diff against an empty database, and is
    # otherwise kept for zero-friction local dev/test on SQLite.) ---
    import sys

    running_migration_command = len(sys.argv) > 1 and sys.argv[1] == "db"

    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(app.config["LOG_DIR"], exist_ok=True)
        if not running_migration_command:
            db.create_all()
            if config_name != "testing":
                from app.services.skills.seed import seed_taxonomy
                from app.services.roadmap.learning_resources import seed_learning_resources

                seed_taxonomy()
                seed_learning_resources()

    # --- Health check for load balancers / uptime monitors ---
    @app.route("/health")
    def health_check():
        from flask import jsonify
        from sqlalchemy import text

        checks = {"database": False}
        status_code = 200
        try:
            db.session.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception:
            status_code = 503

        overall = "ok" if all(checks.values()) else "degraded"
        return jsonify({"status": overall, "checks": checks}), status_code

    return app


def _configure_logging(app: Flask) -> None:
    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    handler = logging.FileHandler(log_path)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.setLevel(logging.INFO)

    root_logger = logging.getLogger("jobmarket_ai")
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    app.logger.setLevel(logging.INFO)
