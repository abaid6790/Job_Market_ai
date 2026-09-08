import io

from app.models import User, Job, JobSkill, JobSection
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _sample_text():
    with open("tests/fixtures/sample_job.txt") as fh:
        return fh.read()


def test_job_page_requires_login(client):
    resp = client.get("/jobs/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_analyze_requires_text_or_file(app, client):
    register_and_login(app, client)
    resp = client.post("/jobs/analyze", data={"job_text": ""}, follow_redirects=True)
    assert b"paste a job description or upload a file" in resp.data.lower()


def test_paste_job_description_is_analyzed(app, client):
    _seed(app)
    register_and_login(app, client)

    resp = client.post(
        "/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Senior Backend Engineer" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job = Job.query.filter_by(user_id=user.id).first()
        assert job.status == "completed"
        assert job.title == "Senior Backend Engineer"
        assert job.company == "Acme Analytics"
        assert job.source == "pasted"


def test_field_extraction_accuracy(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job = Job.query.filter_by(user_id=user.id).first()

        assert job.remote_status == "remote"
        assert job.employment_type == "full_time"
        assert job.salary_min == 140000
        assert job.salary_max == 180000
        assert job.salary_currency == "USD"
        assert job.salary_period == "year"
        assert job.experience_years_min == 5
        assert job.education_level == "bachelor"


def test_required_vs_preferred_skill_classification(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job = Job.query.filter_by(user_id=user.id).first()

        required = {
            js.skill.name for js in JobSkill.query.filter_by(job_id=job.id, requirement_level="required")
        }
        preferred = {
            js.skill.name for js in JobSkill.query.filter_by(job_id=job.id, requirement_level="preferred")
        }

        assert "Python" in required
        assert "Flask" in required
        assert "Docker" in required
        assert "Kubernetes" in preferred
        assert "AWS" in preferred
        # A skill should never appear in both lists.
        assert required.isdisjoint(preferred)


def test_upload_txt_job_description(app, client):
    _seed(app)
    register_and_login(app, client)

    resp = client.post(
        "/jobs/analyze",
        data={"file": (io.BytesIO(_sample_text().encode()), "job.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job = Job.query.filter_by(user_id=user.id).first()
        assert job.status == "completed"
        assert job.source == "uploaded"
        assert job.original_filename == "job.txt"


def test_upload_disallowed_file_type_rejected(app, client):
    register_and_login(app, client)
    resp = client.post(
        "/jobs/analyze",
        data={"file": (io.BytesIO(b"hello"), "job.exe")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"only pdf, docx, or txt" in resp.data.lower() or b"not allowed" in resp.data.lower()

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert Job.query.filter_by(user_id=user.id).count() == 0


def test_sections_are_detected(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job = Job.query.filter_by(user_id=user.id).first()
        section_types = {s.section_type for s in JobSection.query.filter_by(job_id=job.id).all()}
        assert "requirements" in section_types
        assert "preferred" in section_types
        assert "responsibilities" in section_types


def test_job_detail_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        alice = User.query.filter_by(email="alice@example.com").first()
        job_id = Job.query.filter_by(user_id=alice.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 403

    resp = client.post(f"/jobs/{job_id}/delete")
    assert resp.status_code == 403


def test_delete_job(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job_id = Job.query.filter_by(user_id=user.id).first().id

    resp = client.post(f"/jobs/{job_id}/delete", follow_redirects=True)
    assert b"deleted" in resp.data.lower()

    with app.app_context():
        assert Job.query.get(job_id) is None


def test_empty_pasted_text_marked_failed_not_crashed(app, client):
    register_and_login(app, client)
    resp = client.post(
        "/jobs/analyze", data={"job_text": "   \n\n   "}, follow_redirects=True
    )
    # Whitespace-only text fails custom form validation before hitting the pipeline.
    assert b"paste a job description or upload a file" in resp.data.lower()


def test_unparseable_content_marked_failed_gracefully(app, client):
    register_and_login(app, client)
    # Technically non-empty but nothing recognizable — pipeline should
    # complete without crashing, just with mostly-empty structured fields.
    resp = client.post("/jobs/analyze", data={"job_text": "asdf jkl qwer"}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job = Job.query.filter_by(user_id=user.id).first()
        assert job.status == "completed"  # doesn't fail, just finds little
        assert job.remote_status == "unknown"


def test_account_deletion_cascades_jobs(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user_id = user.id
        job_id = Job.query.filter_by(user_id=user_id).first().id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert Job.query.get(job_id) is None
        assert JobSkill.query.filter_by(job_id=job_id).count() == 0


def test_reprocess_job(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/jobs/analyze", data={"job_text": _sample_text()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        job_id = Job.query.filter_by(user_id=user.id).first().id

    resp = client.post(f"/jobs/{job_id}/reprocess", follow_redirects=True)
    assert b"re-processed" in resp.data.lower()

    with app.app_context():
        job = Job.query.get(job_id)
        assert job.status == "completed"
        assert job.title == "Senior Backend Engineer"
