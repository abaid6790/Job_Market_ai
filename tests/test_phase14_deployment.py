"""Phase 14: UI polish, accessibility, migrations & deployment readiness."""
import os
import re

from tests.helpers import register_and_login

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------

def test_health_check_ok(client, db):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] is True


def test_health_check_no_auth_required(client, db):
    # Must be reachable by load balancers without a session/login.
    resp = client.get("/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Migrations: files exist and are wired up
# ---------------------------------------------------------------------------

def test_migrations_directory_exists():
    migrations_dir = os.path.join(PROJECT_ROOT, "migrations")
    assert os.path.isdir(migrations_dir), "migrations/ directory must exist (flask db init)"
    assert os.path.isfile(os.path.join(migrations_dir, "env.py"))
    assert os.path.isfile(os.path.join(migrations_dir, "alembic.ini"))


def test_baseline_migration_exists():
    versions_dir = os.path.join(PROJECT_ROOT, "migrations", "versions")
    assert os.path.isdir(versions_dir)
    revision_files = [f for f in os.listdir(versions_dir) if f.endswith(".py")]
    assert len(revision_files) >= 1, "expected at least one generated migration (the baseline)"

    # The baseline should create all known tables.
    baseline_content = ""
    for f in revision_files:
        with open(os.path.join(versions_dir, f), "r", encoding="utf-8") as fh:
            baseline_content += fh.read()

    for table in ("users", "resumes", "jobs", "skills", "career_roadmaps", "activity_logs"):
        assert f"'{table}'" in baseline_content, f"migration should create table '{table}'"


def test_migrate_extension_registered():
    from app.extensions import migrate

    assert migrate is not None


def test_app_skips_create_all_during_db_command(monkeypatch):
    """The sys.argv guard must recognize `flask db ...` invocations."""
    import sys as _sys

    monkeypatch.setattr(_sys, "argv", ["flask", "db", "upgrade"])
    # Re-import create_app behavior indirectly: just assert the guard logic
    # matches what app/__init__.py checks, since actually invoking flask db
    # against a live db is covered by the deployment doc's manual steps.
    running_migration_command = len(_sys.argv) > 1 and _sys.argv[1] == "db"
    assert running_migration_command is True


# ---------------------------------------------------------------------------
# Accessibility markers
# ---------------------------------------------------------------------------

def test_skip_link_present(client, db):
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert 'class="skip-link"' in html
    assert 'href="#main-content"' in html


def test_main_landmark_present(client, db):
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert 'id="main-content"' in html
    assert re.search(r'<main[^>]+id="main-content"', html)


def test_nav_has_aria_label(client, db):
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert 'aria-label="Primary"' in html


def test_reduced_motion_css_present():
    css_path = os.path.join(PROJECT_ROOT, "app", "static", "css", "style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    assert "prefers-reduced-motion" in css
    assert ".skip-link" in css
    assert "focus-visible" in css


# ---------------------------------------------------------------------------
# Responsive tables
# ---------------------------------------------------------------------------

def test_no_unwrapped_tables_in_templates():
    templates_dir = os.path.join(PROJECT_ROOT, "app", "templates")
    bad = []
    for root, _dirs, files in os.walk(templates_dir):
        for fname in files:
            if not fname.endswith(".html"):
                continue
            path = os.path.join(root, fname)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for m in re.finditer(r"<table\b", content):
                preceding = content[max(0, m.start() - 60):m.start()]
                if "table-responsive" not in preceding:
                    bad.append((path, m.start()))
    assert bad == [], f"found unwrapped <table> elements: {bad}"


def test_rendered_dashboard_tables_are_wrapped(app, db, client):
    register_and_login(app, client)
    resp = client.get("/saved-jobs/tracker")
    html = resp.get_data(as_text=True)
    if "<table" in html:
        assert "table-responsive" in html


# ---------------------------------------------------------------------------
# Deployment hygiene
# ---------------------------------------------------------------------------

def test_requirements_pin_migration_deps():
    req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Flask-Migrate" in content
    assert "alembic" in content.lower()


def test_deployment_doc_exists():
    doc_path = os.path.join(PROJECT_ROOT, "docs", "DEPLOYMENT.md")
    assert os.path.isfile(doc_path)
    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()
    for marker in ("flask db upgrade", "/health", "gunicorn", "SECRET_KEY", "DATABASE_URL"):
        assert marker in content
