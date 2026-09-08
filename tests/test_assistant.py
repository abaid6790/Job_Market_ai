from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import User, AIConversation, AIMessage, Job
from app.services.skills.seed import seed_taxonomy
from app.services.ai.manager import AIProviderManager
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def _openai_payload(text):
    return {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _configure_fake_provider(app):
    with app.app_context():
        from flask import current_app

        fake_manager = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key"}
        )
        current_app.extensions["ai_manager"] = fake_manager


# --- Access control ---

def test_assistant_requires_login(client):
    resp = client.get("/assistant/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_assistant_index_loads_with_no_provider_configured(app, client):
    register_and_login(app, client)
    resp = client.get("/assistant/")
    assert resp.status_code == 200
    assert b"No AI provider is currently configured" in resp.data


# --- Graceful degradation (no provider) ---

def test_starting_conversation_with_no_provider_degrades_gracefully(app, client):
    register_and_login(app, client)
    resp = client.post(
        "/assistant/start", data={"question": "What skills do I need?"}, follow_redirects=True
    )
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        conv = AIConversation.query.filter_by(user_id=user.id).first()
        assert conv is not None
        messages = conv.messages.all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert "no AI provider is configured" in messages[1].content


# --- Mocked provider: grounding correctness ---

def test_conversation_grounded_in_real_profile_data(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post(
        "/profile/",
        data={"target_role": "ML Engineer", "years_experience": "4", "education_level": "master"},
        follow_redirects=True,
    )
    client.post("/profile/skills", data={"skill_name": "Python"}, follow_redirects=True)
    _configure_fake_provider(app)

    captured_system_prompts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured_system_prompts.append(json)
        return _mock_response(200, _openai_payload("You should learn Docker and Kubernetes next."))

    with patch("requests.post", side_effect=fake_post):
        resp = client.post(
            "/assistant/start", data={"question": "What should I learn next?"}, follow_redirects=True
        )

    assert resp.status_code == 200
    assert b"Docker and Kubernetes" in resp.data

    system_content = next(
        m["content"] for m in captured_system_prompts[0]["messages"] if m["role"] == "system"
    )
    assert "ML Engineer" in system_content
    assert "4 years of experience" in system_content
    assert "master" in system_content
    assert "Python" in system_content


def test_context_never_fabricates_data_not_present(app, client):
    _seed(app)
    register_and_login(app, client)

    with app.app_context():
        from app.services.assistant.context_builder import build_user_context

        user = User.query.filter_by(email="alice@example.com").first()
        context, note = build_user_context(user)
        assert "not filled in yet" in context
        assert "none recorded yet" in context
        assert "none uploaded yet" in context
        assert "none yet" in context


def test_specific_job_context_included_when_asking_about_a_job(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post(
        "/jobs/analyze",
        data={"job_text": "Backend Engineer\n\nRequirements\nPython and Docker required.\n"},
        follow_redirects=True,
    )
    _configure_fake_provider(app)

    captured = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        return _mock_response(200, _openai_payload("This role wants Python and Docker."))

    with patch("requests.post", side_effect=fake_post):
        client.post(
            "/assistant/start",
            data={"question": "Explain this job.", "job_id": "1"},
            follow_redirects=True,
        )

    system_content = next(m["content"] for m in captured[0]["messages"] if m["role"] == "system")
    assert "Backend Engineer" in system_content
    assert "Python" in system_content
    assert "Docker" in system_content


def test_followup_question_includes_conversation_history(app, client):
    _seed(app)
    register_and_login(app, client)
    _configure_fake_provider(app)

    with patch("requests.post", return_value=_mock_response(200, _openai_payload("First answer."))):
        client.post("/assistant/start", data={"question": "First question?"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        conv_id = AIConversation.query.filter_by(user_id=user.id).first().id

    captured = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        return _mock_response(200, _openai_payload("Second answer, building on the first."))

    with patch("requests.post", side_effect=fake_post):
        client.post(
            f"/assistant/{conv_id}/ask", data={"question": "Follow-up question?"}, follow_redirects=True
        )

    user_prompt = next(m["content"] for m in captured[0]["messages"] if m["role"] == "user")
    assert "First question?" in user_prompt
    assert "First answer." in user_prompt
    assert "Follow-up question?" in user_prompt


# --- Provider failure (not "unconfigured") is a distinct message ---

def test_provider_configured_but_fails_gives_generic_error_not_no_provider_message(app, client):
    _seed(app)
    register_and_login(app, client)
    _configure_fake_provider(app)

    with patch("requests.post", return_value=_mock_response(500, text="server error")):
        resp = client.post("/assistant/start", data={"question": "Hello?"}, follow_redirects=True)

    assert resp.status_code == 200
    assert b"couldn" in resp.data.lower()
    assert b"no ai provider is configured" not in resp.data.lower()


# --- Ownership / isolation ---

def test_conversation_requires_ownership(app, client):
    register_and_login(app, client, email="alice@example.com", name="Alice")
    client.post("/assistant/start", data={"question": "Hi"}, follow_redirects=True)

    with app.app_context():
        alice = User.query.filter_by(email="alice@example.com").first()
        conv_id = AIConversation.query.filter_by(user_id=alice.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.get(f"/assistant/{conv_id}")
    assert resp.status_code == 403

    resp = client.post(f"/assistant/{conv_id}/ask", data={"question": "hi"})
    assert resp.status_code == 403

    resp = client.post(f"/assistant/{conv_id}/delete")
    assert resp.status_code == 403


def test_two_users_conversations_are_isolated(app, client):
    register_and_login(app, client, email="alice@example.com", name="Alice")
    client.post("/assistant/start", data={"question": "Alices unique question text"}, follow_redirects=True)
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    resp = client.get("/assistant/")
    assert b"Alices unique question text" not in resp.data


def test_delete_conversation(app, client):
    register_and_login(app, client)
    client.post("/assistant/start", data={"question": "Hi"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        conv_id = AIConversation.query.filter_by(user_id=user.id).first().id

    resp = client.post(f"/assistant/{conv_id}/delete", follow_redirects=True)
    assert b"deleted" in resp.data.lower()

    with app.app_context():
        assert AIConversation.query.get(conv_id) is None


def test_account_deletion_cascades_conversations(app, client):
    register_and_login(app, client)
    client.post("/assistant/start", data={"question": "Hi"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user_id = user.id
        conv_id = AIConversation.query.filter_by(user_id=user_id).first().id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert AIConversation.query.get(conv_id) is None
        assert AIMessage.query.filter_by(conversation_id=conv_id).count() == 0


def test_empty_question_rejected(app, client):
    register_and_login(app, client)
    client.post("/assistant/start", data={"question": ""}, follow_redirects=True)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert AIConversation.query.filter_by(user_id=user.id).count() == 0
