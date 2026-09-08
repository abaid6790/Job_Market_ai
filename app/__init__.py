import logging
import os

from flask import Flask, render_template, redirect, url_for, flash, request

from config import config_by_name
from app.extensions import db, login_manager, csrf, limiter


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

    # --- Error handlers ---
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

    # --- DB bootstrap for dev/test (Phase-1 scope; migrations come later) ---
    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(app.config["LOG_DIR"], exist_ok=True)
        db.create_all()
        if config_name != "testing":
            from app.services.skills.seed import seed_taxonomy
            from app.services.roadmap.learning_resources import seed_learning_resources

            seed_taxonomy()
            seed_learning_resources()

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
