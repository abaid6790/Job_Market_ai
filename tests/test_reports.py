from app.extensions import db
from app.models import User, Resume, Job, JobAnalysis
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _setup_full_data(app, client, job_fixture="sample_job.txt"):
    """Upload resume, analyze a job, run a match — the prerequisites for
    most reports."""
    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with open(f"tests/fixtures/{job_fixture}") as fh:
        client.post("/jobs/analyze", data={"job_text": fh.read()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume_id = Resume.query.filter_by(user_id=user.id).first().id
        job_id = Job.query.filter_by(user_id=user.id).first().id

    client.post("/match/analyze", data={"resume_id": resume_id, "job_id": job_id}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        report_id = JobAnalysis.query.filter_by(user_id=user.id).first().id
    return resume_id, job_id, report_id


# --- Access control ---

def test_reports_requires_login(client):
    resp = client.get("/reports/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_reports_index_loads(app, client):
    register_and_login(app, client)
    resp = client.get("/reports/")
    assert resp.status_code == 200
    assert b"Reports" in resp.data


# --- Export formats ---

def test_resume_report_exports_all_formats(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    for fmt, expected_mime in [("json", "application/json"), ("csv", "text/csv"), ("pdf", "application/pdf")]:
        resp = client.get(f"/reports/resume/{resume_id}.{fmt}")
        assert resp.status_code == 200, f"{fmt} export failed"
        assert expected_mime in resp.content_type
        assert len(resp.data) > 0
        assert "attachment" in resp.headers["Content-Disposition"]


def test_match_report_exports_all_formats(app, client):
    _seed(app)
    register_and_login(app, client)
    _, _, report_id = _setup_full_data(app, client)

    for fmt in ("json", "csv", "pdf"):
        resp = client.get(f"/reports/match/{report_id}.{fmt}")
        assert resp.status_code == 200
        assert len(resp.data) > 0


def test_pdf_export_produces_valid_pdf_header(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    resp = client.get(f"/reports/resume/{resume_id}.pdf")
    assert resp.data.startswith(b"%PDF-")  # real PDF, not an error page


def test_json_export_contains_real_resume_data(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    resp = client.get(f"/reports/resume/{resume_id}.json")
    import json

    data = json.loads(resp.data)
    assert data["report_type"] == "Resume Analysis"
    assert data["contact"]["name"] == "Jordan Smith"
    assert "Python" in data["skills"]
    assert len(data["experience"]) == 2


def test_match_report_json_includes_disclaimer(app, client):
    _seed(app)
    register_and_login(app, client)
    _, _, report_id = _setup_full_data(app, client)

    resp = client.get(f"/reports/match/{report_id}.json")
    import json

    data = json.loads(resp.data)
    assert "estimates" in data["disclaimer"].lower()


def test_unsupported_format_returns_404(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    resp = client.get(f"/reports/resume/{resume_id}.xml")
    assert resp.status_code == 404


def test_skill_gap_and_market_reports_export(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_full_data(app, client, "sample_job_gap.txt")

    for fmt in ("json", "csv", "pdf"):
        resp = client.get(f"/reports/skill-gaps.{fmt}")
        assert resp.status_code == 200
        resp = client.get(f"/reports/market.{fmt}")
        assert resp.status_code == 200


def test_roadmap_report_without_roadmap_redirects_with_message(app, client):
    register_and_login(app, client)
    resp = client.get("/reports/roadmap.json", follow_redirects=True)
    assert b"don&#39;t have a career roadmap" in resp.data or b"roadmap" in resp.data.lower()


# --- Ownership ---

def test_resume_report_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    resume_id, _, report_id = _setup_full_data(app, client)

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    assert client.get(f"/reports/resume/{resume_id}.json").status_code == 403
    assert client.get(f"/reports/match/{report_id}.json").status_code == 403
    assert client.get(f"/reports/ats/{report_id}").status_code == 403
    assert client.get(f"/reports/improve/{resume_id}").status_code == 403


# --- ATS analysis ---

def test_ats_analysis_shows_required_disclaimer(app, client):
    _seed(app)
    register_and_login(app, client)
    _, _, report_id = _setup_full_data(app, client)

    resp = client.get(f"/reports/ats/{report_id}")
    assert resp.status_code == 200
    assert b"not an exact representation of any specific employer" in resp.data


def test_ats_analysis_detects_real_missing_skills(app, client):
    _seed(app)
    register_and_login(app, client)
    _, _, report_id = _setup_full_data(app, client, "sample_job_gap.txt")

    with app.app_context():
        report = JobAnalysis.query.get(report_id)
        from app.services.matching.ats_analysis import compute_ats_analysis

        analysis = compute_ats_analysis(report.resume, report.job)
        assert "Terraform" in analysis["required_skills"]["missing"]
        assert "Rust" in analysis["required_skills"]["missing"]
        assert analysis["keyword_coverage"]["score"] is not None


def test_ats_index_without_match_reports_gives_guidance(app, client):
    register_and_login(app, client)
    resp = client.get("/reports/ats")
    assert b"match report" in resp.data.lower()


# --- Resume improvement ---

def test_improvement_analysis_never_invents_content(app, client):
    """The deterministic analysis must only reference bullets that
    actually exist in the resume."""
    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    with app.app_context():
        resume = Resume.query.get(resume_id)
        from app.services.resume.improvement import analyze_resume

        analysis = analyze_resume(resume)
        resume_text_lower = (resume.raw_text or "").lower()
        for wb in analysis["weak_bullets"]:
            # Every flagged bullet must be real text from the resume.
            assert wb["text"].lower() in resume_text_lower


def test_improvement_detects_missing_skills_against_job(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id, _ = _setup_full_data(app, client, "sample_job_gap.txt")

    resp = client.get(f"/reports/improve/{resume_id}?job_id={job_id}")
    assert resp.status_code == 200
    assert b"Terraform" in resp.data or b"Rust" in resp.data


def test_improvement_ai_degrades_gracefully_without_provider(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    resp = client.post(f"/reports/improve/{resume_id}/ai", follow_redirects=True)
    assert resp.status_code == 200
    assert b"no AI provider is configured" in resp.data.lower() or b"aren&#39;t available" in resp.data


def test_improvement_ai_uses_provider_when_configured(app, client):
    from unittest.mock import patch, MagicMock

    _seed(app)
    register_and_login(app, client)
    resume_id, _, _ = _setup_full_data(app, client)

    with app.app_context():
        from flask import current_app
        from app.services.ai.manager import AIProviderManager

        current_app.extensions["ai_manager"] = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key"}
        )

    captured = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": "Consider quantifying your Docker migration bullet."}}],
            "usage": {},
        }
        return resp

    with patch("requests.post", side_effect=fake_post):
        resp = client.post(f"/reports/improve/{resume_id}/ai", follow_redirects=True)

    assert b"quantifying your Docker migration" in resp.data
    # The system prompt must forbid inventing content.
    system_msg = next(m["content"] for m in captured[0]["messages"] if m["role"] == "system")
    assert "NEVER invent" in system_msg


def test_improve_index_without_resume_gives_guidance(app, client):
    register_and_login(app, client)
    resp = client.get("/reports/improve")
    assert b"Upload a resume" in resp.data
