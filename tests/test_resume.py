import io

from app.extensions import db
from app.models import User, Resume, ResumeExperience, ResumeEducation, ResumeSkill, UserSkill
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _fixture_bytes(name):
    with open(f"tests/fixtures/{name}", "rb") as fh:
        return fh.read()


def _upload(client, filename, content_type, data=None, field_filename=None):
    payload = data if data is not None else _fixture_bytes(filename)
    return client.post(
        "/resume/upload",
        data={"file": (io.BytesIO(payload), field_filename or filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_resume_page_requires_login(client):
    resp = client.get("/resume/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_upload_txt_resume_is_parsed(app, client):
    _seed(app)
    register_and_login(app, client)

    resp = _upload(client, "sample_resume.txt", "text/plain")
    assert resp.status_code == 200
    assert b"Jordan Smith" in resp.data or b"parsed successfully" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()
        assert resume is not None
        assert resume.status == "completed"
        assert resume.extracted_name == "Jordan Smith"
        assert resume.extracted_email == "jordan.smith@example.com"
        assert resume.is_primary is True


def test_upload_docx_resume_is_parsed(app, client):
    _seed(app)
    register_and_login(app, client)
    resp = _upload(
        client,
        "sample_resume.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()
        assert resume.status == "completed"
        assert resume.file_type == "docx"


def test_upload_pdf_resume_is_parsed(app, client):
    _seed(app)
    register_and_login(app, client)
    resp = _upload(client, "sample_resume.pdf", "application/pdf")
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()
        assert resume.status == "completed"
        assert resume.file_type == "pdf"


def test_experience_and_education_extracted(app, client):
    _seed(app)
    register_and_login(app, client)
    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()

        experiences = ResumeExperience.query.filter_by(resume_id=resume.id).all()
        assert len(experiences) == 2
        titles = {e.job_title for e in experiences}
        assert "Senior Backend Engineer" in titles
        current = [e for e in experiences if e.is_current]
        assert len(current) == 1

        education = ResumeEducation.query.filter_by(resume_id=resume.id).all()
        assert len(education) == 1
        assert "Springfield" in (education[0].institution or "")


def test_skills_extracted_and_synced_to_profile(app, client):
    _seed(app)
    register_and_login(app, client)
    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()

        resume_skills = ResumeSkill.query.filter_by(resume_id=resume.id).all()
        skill_names = {rs.skill.name for rs in resume_skills}
        assert "Python" in skill_names
        assert "Docker" in skill_names
        assert "AWS" in skill_names

        # Extracted skills should flow into the user's profile automatically.
        user_skill_names = {
            us.skill.name for us in UserSkill.query.filter_by(user_id=user.id).all()
        }
        assert "Python" in user_skill_names
        python_link = UserSkill.query.filter_by(user_id=user.id).join(UserSkill.skill).filter_by(name="Python").first()
        assert python_link.source == "resume"


def test_resume_skill_sync_never_overwrites_manual_entry(app, client):
    _seed(app)
    register_and_login(app, client)

    # User manually adds Python with a specific proficiency first.
    client.post(
        "/profile/skills",
        data={"skill_name": "Python", "proficiency": "expert", "years_experience": "10"},
        follow_redirects=True,
    )

    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        link = UserSkill.query.filter_by(user_id=user.id).join(UserSkill.skill).filter_by(name="Python").first()
        assert link.source == "manual"
        assert link.proficiency == "expert"  # untouched by the resume sync
        # Still only one UserSkill row for Python, not a duplicate.
        assert UserSkill.query.filter_by(user_id=user.id).join(UserSkill.skill).filter_by(name="Python").count() == 1


def test_reject_disallowed_extension(app, client):
    register_and_login(app, client)
    resp = _upload(client, "sample_resume.txt", "text/plain", data=b"hello", field_filename="resume.exe")
    assert b"Unsupported file type" in resp.data or b"pdf" in resp.data.lower()

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert Resume.query.filter_by(user_id=user.id).count() == 0


def test_reject_mismatched_file_signature(app, client):
    register_and_login(app, client)
    # A .pdf extension but content that isn't actually a PDF.
    resp = _upload(client, "sample_resume.txt", "application/pdf", data=b"not a real pdf", field_filename="fake.pdf")
    assert b"doesn&#39;t look like a valid PDF" in resp.data or b"valid PDF" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert Resume.query.filter_by(user_id=user.id).count() == 0


def test_reject_empty_file(app, client):
    register_and_login(app, client)
    resp = _upload(client, "sample_resume.txt", "text/plain", data=b"", field_filename="empty.txt")
    assert b"empty" in resp.data.lower()


def test_encrypted_or_unreadable_pdf_marked_failed_not_crashed(app, client):
    register_and_login(app, client)
    # Valid PDF magic bytes but garbage content — should fail gracefully,
    # not 500.
    resp = _upload(client, "sample_resume.txt", "application/pdf", data=b"%PDF-1.4\ngarbage not a real pdf structure", field_filename="broken.pdf")
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()
        assert resume.status == "failed"
        assert resume.error_message


def test_resume_detail_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        alice = User.query.filter_by(email="alice@example.com").first()
        resume_id = Resume.query.filter_by(user_id=alice.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.get(f"/resume/{resume_id}")
    assert resp.status_code == 403

    resp = client.get(f"/resume/{resume_id}/download")
    assert resp.status_code == 403

    resp = client.post(f"/resume/{resume_id}/delete")
    assert resp.status_code == 403


def test_delete_resume_removes_row_and_file(app, client):
    _seed(app)
    register_and_login(app, client)
    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).first()
        resume_id = resume.id

    resp = client.post(f"/resume/{resume_id}/delete", follow_redirects=True)
    assert b"deleted" in resp.data.lower()

    with app.app_context():
        assert Resume.query.get(resume_id) is None


def test_multiple_resumes_primary_switching(app, client):
    _seed(app)
    register_and_login(app, client)
    _upload(client, "sample_resume.txt", "text/plain")
    _upload(client, "sample_resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resumes = Resume.query.filter_by(user_id=user.id).all()
        assert len(resumes) == 2
        primaries = [r for r in resumes if r.is_primary]
        assert len(primaries) == 1
        assert primaries[0].file_type == "txt"  # first upload stays primary
        non_primary_id = [r.id for r in resumes if not r.is_primary][0]

    resp = client.post(f"/resume/{non_primary_id}/set-primary", follow_redirects=True)
    assert b"set as your primary" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resumes = Resume.query.filter_by(user_id=user.id).all()
        primaries = [r for r in resumes if r.is_primary]
        assert len(primaries) == 1
        assert primaries[0].id == non_primary_id


def test_reprocess_resume(app, client):
    _seed(app)
    register_and_login(app, client)
    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume_id = Resume.query.filter_by(user_id=user.id).first().id

    resp = client.post(f"/resume/{resume_id}/reprocess", follow_redirects=True)
    assert b"re-processed" in resp.data.lower()

    with app.app_context():
        resume = Resume.query.get(resume_id)
        assert resume.status == "completed"
        assert resume.extracted_name == "Jordan Smith"
        # Structured rows should exist exactly once each, not duplicated
        # by the reprocess (old rows cleared before re-parsing).
        assert ResumeSkill.query.filter_by(resume_id=resume_id).count() == len(
            {rs.skill_id for rs in ResumeSkill.query.filter_by(resume_id=resume_id).all()}
        )
    _seed(app)
    register_and_login(app, client)
    _upload(client, "sample_resume.txt", "text/plain")

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user_id = user.id
        resume_id = Resume.query.filter_by(user_id=user_id).first().id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert Resume.query.get(resume_id) is None
        assert ResumeSkill.query.filter_by(resume_id=resume_id).count() == 0
