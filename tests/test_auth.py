from app.extensions import db
from app.models import User, EmailVerificationToken, PasswordResetToken


def register(client, email="alice@example.com", password="Password123", name="Alice"):
    return client.post(
        "/auth/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )


def login(client, email="alice@example.com", password="Password123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_register_creates_unverified_user(app, client):
    resp = register(client)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert user is not None
        assert user.is_email_verified is False
        assert user.password_hash != "Password123"  # never store plaintext
        assert user.check_password("Password123")


def test_duplicate_registration_does_not_leak_existence(app, client):
    register(client)
    resp = register(client)
    assert resp.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="alice@example.com").count() == 1


def test_weak_password_rejected(client):
    resp = client.post(
        "/auth/register",
        data={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert b"at least 8 characters" in resp.data


def test_login_before_verification_redirects_to_verify_notice(app, client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    assert b"Check your inbox" in resp.data


def test_dashboard_blocked_until_verified(app, client):
    register(client)
    login(client)
    resp = client.get("/dashboard/", follow_redirects=True)
    assert b"Check your inbox" in resp.data


def test_full_verification_flow_unlocks_dashboard(app, client):
    register(client)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        token = EmailVerificationToken.query.filter_by(user_id=user.id).first()
        token_value = token.token

    resp = client.get(f"/auth/verify-email/{token_value}", follow_redirects=True)
    assert b"verified" in resp.data.lower()

    login(client)
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert b"Welcome, Alice" in resp.data


def test_verification_token_cannot_be_reused(app, client):
    register(client)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        token_value = EmailVerificationToken.query.filter_by(user_id=user.id).first().token

    client.get(f"/auth/verify-email/{token_value}")
    resp = client.get(f"/auth/verify-email/{token_value}", follow_redirects=True)
    assert b"invalid or has expired" in resp.data


def test_wrong_password_rejected(client):
    register(client)
    resp = login(client, password="WrongPassword1")
    assert b"Invalid email or password" in resp.data


def _verify_user(app, client, email="alice@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        token = EmailVerificationToken.query.filter_by(user_id=user.id).first()
        token_value = token.token
    client.get(f"/auth/verify-email/{token_value}")


def test_forgot_and_reset_password_flow(app, client):
    register(client)
    _verify_user(app, client)

    client.post("/auth/forgot-password", data={"email": "alice@example.com"})
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        reset_token = PasswordResetToken.query.filter_by(user_id=user.id).first()
        token_value = reset_token.token

    resp = client.post(
        f"/auth/reset-password/{token_value}",
        data={"password": "NewPassword123", "confirm_password": "NewPassword123"},
        follow_redirects=True,
    )
    assert b"password has been reset" in resp.data.lower()

    # Old password should no longer work.
    resp = login(client, password="Password123")
    assert b"Invalid email or password" in resp.data

    # New password should work.
    resp = login(client, password="NewPassword123")
    assert resp.status_code == 200
    assert b"Welcome, Alice" in resp.data


def test_reset_token_single_use(app, client):
    register(client)
    _verify_user(app, client)
    client.post("/auth/forgot-password", data={"email": "alice@example.com"})
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        token_value = PasswordResetToken.query.filter_by(user_id=user.id).first().token

    client.post(
        f"/auth/reset-password/{token_value}",
        data={"password": "NewPassword123", "confirm_password": "NewPassword123"},
    )
    resp = client.post(
        f"/auth/reset-password/{token_value}",
        data={"password": "AnotherPass123", "confirm_password": "AnotherPass123"},
        follow_redirects=True,
    )
    assert b"invalid or has expired" in resp.data


def test_change_password_requires_current_password(app, client):
    register(client)
    _verify_user(app, client)
    login(client)

    resp = client.post(
        "/auth/change-password",
        data={
            "current_password": "WrongCurrent1",
            "new_password": "BrandNew123",
            "confirm_password": "BrandNew123",
        },
        follow_redirects=True,
    )
    assert b"current password is incorrect" in resp.data.lower()

    resp = client.post(
        "/auth/change-password",
        data={
            "current_password": "Password123",
            "new_password": "BrandNew123",
            "confirm_password": "BrandNew123",
        },
        follow_redirects=True,
    )
    assert b"password has been changed" in resp.data.lower()


def test_logout_blocks_dashboard_access(app, client):
    register(client)
    _verify_user(app, client)
    login(client)
    client.get("/auth/logout")
    resp = client.get("/dashboard/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_delete_account_removes_user_and_data(app, client):
    register(client)
    _verify_user(app, client)
    login(client)

    resp = client.post(
        "/auth/delete-account",
        data={"password": "Password123"},
        follow_redirects=True,
    )
    assert b"deleted" in resp.data.lower()

    with app.app_context():
        assert User.query.filter_by(email="alice@example.com").first() is None


def test_csrf_protection_enabled_outside_testing_config():
    # Sanity check: CSRF is explicitly disabled only in TestingConfig,
    # so it remains enforced in development/production.
    from config import DevelopmentConfig, TestingConfig

    assert getattr(TestingConfig, "WTF_CSRF_ENABLED", True) is False
    assert not hasattr(DevelopmentConfig, "WTF_CSRF_ENABLED") or DevelopmentConfig.WTF_CSRF_ENABLED is not False


def test_unauthenticated_user_redirected_from_dashboard(client):
    resp = client.get("/dashboard/", follow_redirects=True)
    assert b"log in" in resp.data.lower()
