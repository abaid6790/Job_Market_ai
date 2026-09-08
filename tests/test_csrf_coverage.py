"""
Regression test for a real bug: several action buttons (delete, reprocess,
set-primary, deactivate) were rendered as bare `<form method="POST">` with
no CSRF token field at all. Flask-WTF's CSRFProtect correctly rejected
those submissions with 400 "CSRF token is missing" — which is the right
security behavior, but it meant the buttons were completely non-functional
for a real browser user. Caught by testing with WTF_CSRF_ENABLED actually
on (the testing config disables it, so pytest alone couldn't catch this).

This test re-enables CSRF for a real (non-test-client-bypassed) app and
scans every POST <form> on key pages for a csrf_token field, so this class
of bug can't silently return.
"""
import re

from app import create_app
from app.extensions import db
from app.services.skills.seed import seed_taxonomy


def _make_csrf_enabled_client():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    return app, app.test_client()


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match, "No csrf_token found on page — check the fixture page itself"
    return match.group(1)


def _register_verify_login(app, client, email="alice@example.com", password="Password123", name="Alice"):
    """Like tests.helpers.register_and_login, but fetches and submits a
    real CSRF token at each step — required because this test suite
    deliberately keeps CSRF enforcement ON (unlike the normal test config)."""
    from app.models import User, EmailVerificationToken

    register_page = client.get("/auth/register").data.decode()
    csrf = _extract_csrf(register_page)
    client.post(
        "/auth/register",
        data={
            "csrf_token": csrf,
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None, "Registration failed — check the CSRF token extraction"
        token = EmailVerificationToken.query.filter_by(user_id=user.id).first().token
    client.get(f"/auth/verify-email/{token}")

    login_page = client.get("/auth/login").data.decode()
    csrf = _extract_csrf(login_page)
    client.post(
        "/auth/login",
        data={"csrf_token": csrf, "email": email, "password": password},
        follow_redirects=True,
    )


def _make_csrf_enabled_client():
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    return app, app.test_client()


def _assert_all_post_forms_have_csrf(html: str, page_name: str, require_forms: bool = True):
    forms = re.findall(r'<form\s+method="POST".*?</form>', html, re.IGNORECASE | re.DOTALL)
    if require_forms:
        assert forms, f"No POST forms found on {page_name} — check the test setup itself"
    for form_html in forms:
        assert "csrf_token" in form_html, (
            f"A POST form on {page_name} is missing a csrf_token field "
            f"(would 400 for a real browser user): {form_html[:120]}..."
        )


def test_resume_pages_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        upload_page = client.get("/resume/").data.decode()
        csrf = _extract_csrf(upload_page)
        client.post(
            "/resume/upload",
            data={"csrf_token": csrf, "file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    resp = client.get("/resume/")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "resume list")

    resp = client.get("/resume/1")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "resume detail (completed)", require_forms=False)


def test_job_pages_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    with open("tests/fixtures/sample_job.txt") as fh:
        text = fh.read()
    jobs_page = client.get("/jobs/").data.decode()
    csrf = _extract_csrf(jobs_page)
    client.post("/jobs/analyze", data={"csrf_token": csrf, "job_text": text}, follow_redirects=True)

    resp = client.get("/jobs/")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "job list")

    resp = client.get("/jobs/1")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "job detail (completed)", require_forms=False)


def test_profile_page_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)
    profile_page = client.get("/profile/").data.decode()
    csrf = _extract_csrf(profile_page)
    client.post("/profile/skills", data={"csrf_token": csrf, "skill_name": "Python"}, follow_redirects=True)
    profile_page = client.get("/profile/").data.decode()
    csrf = _extract_csrf(profile_page)
    client.post("/profile/certifications", data={"csrf_token": csrf, "name": "PMP"}, follow_redirects=True)

    resp = client.get("/profile/")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "profile page")


def test_admin_taxonomy_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    with app.app_context():
        from app.models import User
        user = User.query.filter_by(email="alice@example.com").first()
        user.is_admin = True
        db.session.commit()

    resp = client.get("/admin/taxonomy")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "admin taxonomy")


def test_admin_data_import_form_has_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    with app.app_context():
        from app.models import User
        user = User.query.filter_by(email="alice@example.com").first()
        user.is_admin = True
        db.session.commit()

    resp = client.get("/admin/data-import")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "admin data import")


def test_matching_pages_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        upload_page = client.get("/resume/").data.decode()
        csrf = _extract_csrf(upload_page)
        client.post(
            "/resume/upload",
            data={"csrf_token": csrf, "file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with open("tests/fixtures/sample_job.txt") as fh:
        text = fh.read()
    jobs_page = client.get("/jobs/").data.decode()
    csrf = _extract_csrf(jobs_page)
    client.post("/jobs/analyze", data={"csrf_token": csrf, "job_text": text}, follow_redirects=True)

    match_page = client.get("/match/").data.decode()
    csrf = _extract_csrf(match_page)
    client.post(
        "/match/analyze",
        data={"csrf_token": csrf, "resume_id": 1, "job_id": 1},
        follow_redirects=True,
    )

    resp = client.get("/match/")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "match index", require_forms=False)

    resp = client.get("/match/1")
    _assert_all_post_forms_have_csrf(resp.data.decode(), "match detail")


def test_job_search_and_saved_jobs_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    jobs_page = client.get("/jobs/").data.decode()
    csrf = _extract_csrf(jobs_page)
    client.post(
        "/jobs/analyze",
        data={"csrf_token": csrf, "job_text": "Backend Engineer\n\nRequirements\nPython required.\n"},
        follow_redirects=True,
    )

    browse_page = client.get("/jobs/search/1").data.decode()
    _assert_all_post_forms_have_csrf(browse_page, "job browse detail")

    csrf = _extract_csrf(browse_page)
    client.post("/jobs/search/1/save", data={"csrf_token": csrf}, follow_redirects=True)

    saved_page = client.get("/saved-jobs/").data.decode()
    _assert_all_post_forms_have_csrf(saved_page, "saved jobs index")


def test_assistant_pages_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    index_page = client.get("/assistant/").data.decode()
    _assert_all_post_forms_have_csrf(index_page, "assistant index")

    csrf = _extract_csrf(index_page)
    client.post("/assistant/start", data={"csrf_token": csrf, "question": "Hello?"}, follow_redirects=True)

    conv_page = client.get("/assistant/1").data.decode()
    _assert_all_post_forms_have_csrf(conv_page, "assistant conversation")


def test_roadmap_pages_forms_have_csrf():
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
        from app.services.roadmap.learning_resources import seed_learning_resources

        seed_learning_resources()
    _register_verify_login(app, client)

    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        upload_page = client.get("/resume/").data.decode()
        csrf = _extract_csrf(upload_page)
        client.post(
            "/resume/upload",
            data={"csrf_token": csrf, "file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with open("tests/fixtures/sample_job_gap.txt") as fh:
        text = fh.read()
    jobs_page = client.get("/jobs/").data.decode()
    csrf = _extract_csrf(jobs_page)
    client.post("/jobs/analyze", data={"csrf_token": csrf, "job_text": text}, follow_redirects=True)

    match_page = client.get("/match/").data.decode()
    csrf = _extract_csrf(match_page)
    client.post(
        "/match/analyze",
        data={"csrf_token": csrf, "resume_id": 1, "job_id": 1},
        follow_redirects=True,
    )

    roadmap_page = client.get("/roadmap/").data.decode()
    _assert_all_post_forms_have_csrf(roadmap_page, "roadmap index (empty)")

    csrf = _extract_csrf(roadmap_page)
    client.post("/roadmap/generate", data={"csrf_token": csrf}, follow_redirects=True)
    client.post("/roadmap/recommendations/generate", data={"csrf_token": csrf}, follow_redirects=True)

    roadmap_page = client.get("/roadmap/").data.decode()
    _assert_all_post_forms_have_csrf(roadmap_page, "roadmap index (populated)")


def test_retry_button_actually_works_with_csrf_enabled():
    """End-to-end: force a failed resume parse (so the "Retry" form
    actually renders), extract its CSRF token exactly as a browser would
    from that specific form's HTML, and confirm clicking it works."""
    app, client = _make_csrf_enabled_client()
    with app.app_context():
        seed_taxonomy()
    _register_verify_login(app, client)

    upload_page = client.get("/resume/").data.decode()
    csrf = _extract_csrf(upload_page)
    # Valid PDF magic bytes but unparseable content — reliably produces a
    # "failed" status so the conditional Retry form actually renders.
    import io

    client.post(
        "/resume/upload",
        data={
            "csrf_token": csrf,
            "file": (io.BytesIO(b"%PDF-1.4\ngarbage not a real pdf structure"), "broken.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    detail_html = client.get("/resume/1").data.decode()
    assert "failed" in detail_html.lower()

    match = re.search(
        r'<form\s+method="POST"[^>]*reprocess.*?</form>', detail_html, re.IGNORECASE | re.DOTALL
    )
    assert match, "Retry form not found on a failed resume's detail page"
    assert "csrf_token" in match.group(0), "Retry form is missing its CSRF token"

    token_match = re.search(r'name="csrf_token" value="([^"]+)"', match.group(0))
    assert token_match, "Retry form's CSRF input has no value"

    resp = client.post(
        "/resume/1/reprocess", data={"csrf_token": token_match.group(1)}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"re-processed" in resp.data.lower()
