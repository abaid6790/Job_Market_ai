from app.extensions import db
from app.models import User, ActivityLog
from tests.helpers import register_and_login


def _make_admin(app, email="alice@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        user.is_admin = True
        db.session.commit()
        return user.id


# --- Security headers ---

def test_security_headers_present_on_every_response(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in resp.headers
    assert "Permissions-Policy" in resp.headers
    csp = resp.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "default-src 'self'" in csp


def test_hsts_not_set_in_debug_mode(client):
    # TestingConfig has DEBUG=True — HSTS on a non-HTTPS dev server would
    # be actively harmful (browsers would pin it), so it must be absent.
    resp = client.get("/")
    assert "Strict-Transport-Security" not in resp.headers


# --- Audit logging ---

def test_successful_login_is_audited(app, client):
    register_and_login(app, client)
    with app.app_context():
        entry = ActivityLog.query.filter_by(action="login_success").first()
        assert entry is not None
        assert entry.category == "auth"
        assert entry.user_email == "alice@example.com"


def test_failed_login_is_audited(app, client):
    register_and_login(app, client)
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "alice@example.com", "password": "WrongPass1"}, follow_redirects=True)

    with app.app_context():
        entry = ActivityLog.query.filter_by(action="login_failed").first()
        assert entry is not None
        assert entry.category == "auth"


def test_registration_and_password_change_audited(app, client):
    register_and_login(app, client)
    client.post(
        "/auth/change-password",
        data={"current_password": "Password123", "new_password": "NewPassword123", "confirm_password": "NewPassword123"},
        follow_redirects=True,
    )
    with app.app_context():
        assert ActivityLog.query.filter_by(action="register").count() == 1
        assert ActivityLog.query.filter_by(action="password_changed").count() == 1


def test_audit_log_never_stores_passwords_or_secrets(app, client):
    """The redaction backstop must strip anything secret-looking even if
    a caller passes it in by mistake."""
    register_and_login(app, client)
    with app.app_context():
        from app.services.auth.audit import log_event

        log_event("security", "test_event", description="password=hunter2 and api_key=sk-abc123456789")
        entry = ActivityLog.query.filter_by(action="test_event").first()
        assert "hunter2" not in entry.description
        assert "sk-abc123456789" not in entry.description
        assert "[REDACTED]" in entry.description


def test_audit_log_survives_user_deletion(app, client):
    """An audit trail that can be erased by deleting the account isn't an
    audit trail."""
    register_and_login(app, client)
    with app.app_context():
        before = ActivityLog.query.count()
        assert before > 0

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert ActivityLog.query.count() >= before
        entry = ActivityLog.query.filter_by(action="account_deleted").first()
        assert entry is not None
        assert entry.user_email == "alice@example.com"  # denormalized, survives


# --- Admin access control ---

def test_all_admin_pages_require_admin(app, client):
    register_and_login(app, client)
    for path in ("/admin/users", "/admin/audit-log", "/admin/overview"):
        assert client.get(path).status_code == 403, f"{path} was not admin-gated"


def test_admin_pages_load_for_admin(app, client):
    register_and_login(app, client)
    _make_admin(app)
    for path in ("/admin/users", "/admin/audit-log", "/admin/overview"):
        assert client.get(path).status_code == 200, f"{path} failed for admin"


# --- User management ---

def test_admin_can_disable_and_enable_user(app, client):
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _make_admin(app)

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    with app.app_context():
        bob_id = User.query.filter_by(email="bob@example.com").first().id
    client.get("/auth/logout")

    register_and_login(app, client, email="alice@example.com", password="Password123", name="Alice")

    resp = client.post(f"/admin/users/{bob_id}/toggle-active", follow_redirects=True)
    assert b"disabled" in resp.data.lower()
    with app.app_context():
        assert User.query.get(bob_id).is_active_account is False
        assert ActivityLog.query.filter_by(action="user_disabled").count() == 1

    resp = client.post(f"/admin/users/{bob_id}/toggle-active", follow_redirects=True)
    with app.app_context():
        assert User.query.get(bob_id).is_active_account is True


def test_disabled_user_cannot_log_in(app, client):
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _make_admin(app)
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    with app.app_context():
        bob_id = User.query.filter_by(email="bob@example.com").first().id
    client.get("/auth/logout")

    register_and_login(app, client, email="alice@example.com", password="Password123", name="Alice")
    client.post(f"/admin/users/{bob_id}/toggle-active", follow_redirects=True)
    client.get("/auth/logout")

    resp = client.post(
        "/auth/login", data={"email": "bob@example.com", "password": "Password123"}, follow_redirects=True
    )
    assert b"disabled" in resp.data.lower()
    with app.app_context():
        assert ActivityLog.query.filter_by(action="login_disabled_account").count() == 1


def test_admin_cannot_disable_own_account(app, client):
    register_and_login(app, client)
    admin_id = _make_admin(app)

    resp = client.post(f"/admin/users/{admin_id}/toggle-active", follow_redirects=True)
    assert b"can&#39;t disable your own account" in resp.data or b"own account" in resp.data
    with app.app_context():
        assert User.query.get(admin_id).is_active_account is True


def test_admin_cannot_revoke_own_admin_rights(app, client):
    register_and_login(app, client)
    admin_id = _make_admin(app)

    resp = client.post(f"/admin/users/{admin_id}/toggle-admin", follow_redirects=True)
    assert b"own admin status" in resp.data
    with app.app_context():
        assert User.query.get(admin_id).is_admin is True


def test_admin_can_grant_and_revoke_admin_to_others(app, client):
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _make_admin(app)
    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    with app.app_context():
        bob_id = User.query.filter_by(email="bob@example.com").first().id
    client.get("/auth/logout")
    register_and_login(app, client, email="alice@example.com", password="Password123", name="Alice")

    client.post(f"/admin/users/{bob_id}/toggle-admin", follow_redirects=True)
    with app.app_context():
        assert User.query.get(bob_id).is_admin is True
        assert ActivityLog.query.filter_by(action="admin_granted").count() == 1


def test_user_search_filters_results(app, client):
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _make_admin(app)
    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    client.get("/auth/logout")
    register_and_login(app, client, email="alice@example.com", password="Password123", name="Alice")

    resp = client.get("/admin/users?q=bob")
    assert b"bob@example.com" in resp.data
    assert b"alice@example.com" not in resp.data


# --- Admin overview ---

def test_overview_shows_real_counts(app, client):
    register_and_login(app, client)
    _make_admin(app)
    resp = client.get("/admin/overview")
    assert resp.status_code == 200
    assert b"Users" in resp.data
    assert b"Audit entries" in resp.data


def test_audit_log_category_filter(app, client):
    register_and_login(app, client)
    _make_admin(app)
    resp = client.get("/admin/audit-log?category=auth")
    assert resp.status_code == 200
    assert b"login_success" in resp.data


# --- 403 handler ---

def test_403_renders_friendly_page_not_raw_error(app, client):
    register_and_login(app, client)
    resp = client.get("/admin/users")
    assert resp.status_code == 403
    assert b"403" in resp.data
    assert b"permission" in resp.data.lower()
