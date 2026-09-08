from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import User
from tests.helpers import register_and_login


def _make_admin(app, email="alice@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        user.is_admin = True
        db.session.commit()


def test_ai_status_requires_admin(app, client):
    register_and_login(app, client)
    resp = client.get("/admin/ai-status")
    assert resp.status_code == 403


def test_ai_status_shows_no_providers_message_when_unconfigured(app, client):
    register_and_login(app, client)
    _make_admin(app)
    resp = client.get("/admin/ai-status")
    assert resp.status_code == 200
    assert b"No AI providers are configured" in resp.data


def test_ai_status_page_never_leaks_full_api_key(app, client):
    """Even if a Gemini key were configured, the status page must only
    ever show the last few characters, never the full secret."""
    register_and_login(app, client)
    _make_admin(app)

    with app.app_context():
        from app.services.ai.manager import AIProviderManager

        fake_manager = AIProviderManager(
            {
                "AI_PROVIDER": "gemini",
                "AI_PROVIDER_ORDER": ["gemini"],
                "GEMINI_API_KEYS": ["sk-supersecretgeminikey12345"],
            }
        )
        app.extensions["ai_manager"] = fake_manager

    resp = client.get("/admin/ai-status")
    assert resp.status_code == 200
    assert b"supersecret" not in resp.data
    assert b"2345" in resp.data  # last 4 chars are fine to show


def test_ai_status_shows_usage_stats_after_a_logged_request(app, client):
    register_and_login(app, client)
    _make_admin(app)

    with app.app_context():
        from app.services.ai.usage import log_usage

        log_usage(provider="openai", method="generate", success=True, response_time_ms=250)
        log_usage(provider="openai", method="generate", success=False, error_message="boom")

    resp = client.get("/admin/ai-status")
    assert resp.status_code == 200
    assert b"Total requests" in resp.data
    assert b"50.0%" in resp.data or b"Success rate" in resp.data
