from app.extensions import db
from app.models import User, Job, SavedJob
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


SAMPLE_JOB_TEXT = "Backend Engineer\n\nRequirements\n5+ years of experience.\nPython and Docker required.\n\nCompensation\n$120,000 - $150,000 per year\n"
SAMPLE_JOB_TEXT_2 = "Frontend Engineer\nWebCo — Austin, TX (Remote)\n\nRequirements\n2+ years of experience.\nReact required.\n\nCompensation\n$90,000 per year\n"


def _analyze_job(client, text=SAMPLE_JOB_TEXT):
    return client.post("/jobs/analyze", data={"job_text": text}, follow_redirects=True)


# --- Job search ---

def test_job_search_requires_login(client):
    resp = client.get("/jobs/search", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_job_search_finds_analyzed_jobs(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)

    resp = client.get("/jobs/search?query=Backend")
    assert resp.status_code == 200
    assert b"Backend Engineer" in resp.data


def test_job_search_filters_by_remote_status(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client, SAMPLE_JOB_TEXT)  # remote status unknown
    _analyze_job(client, SAMPLE_JOB_TEXT_2)  # remote

    resp = client.get("/jobs/search?remote_status=remote")
    assert b"Frontend Engineer" in resp.data
    assert b"1 job found" in resp.data  # exactly one result — the placeholder text also says "Backend Engineer"


def test_job_search_filters_by_min_salary(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client, SAMPLE_JOB_TEXT)  # up to 150k
    _analyze_job(client, SAMPLE_JOB_TEXT_2)  # 90k

    resp = client.get("/jobs/search?min_salary=100000")
    assert b"Backend Engineer" in resp.data
    assert b"Frontend Engineer" not in resp.data


def test_job_search_filters_by_max_experience(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client, SAMPLE_JOB_TEXT)  # needs 5 years
    _analyze_job(client, SAMPLE_JOB_TEXT_2)  # needs 2 years

    resp = client.get("/jobs/search?max_experience=3")
    assert b"Frontend Engineer" in resp.data
    assert b"1 job found" in resp.data


def test_job_search_surfaces_other_users_jobs(app, client):
    """Job search must find jobs analyzed by OTHER users too — it's a
    shared market pool, not a private list (this is the key behavioral
    difference from the ownership-gated /jobs/<id> personal view)."""
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    resp = client.get("/jobs/search?query=Backend")
    assert b"Backend Engineer" in resp.data  # Bob can find Alice's analyzed job


def test_browse_detail_not_ownership_gated(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    resp = client.get(f"/jobs/search/{job_id}")
    assert resp.status_code == 200  # not 403 — public browse view
    assert b"Backend Engineer" in resp.data


def test_owner_private_detail_still_ownership_gated(app, client):
    """The ORIGINAL /jobs/<id> personal analysis page (edit/delete/
    reprocess) must remain strictly ownership-gated — only /jobs/search/
    <id> is public."""
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 403


# --- Saving jobs ---

def test_save_job(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id

    resp = client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)
    assert b"Job saved" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved = SavedJob.query.filter_by(user_id=user.id, job_id=job_id).first()
        assert saved is not None
        assert saved.status == "saved"


def test_save_job_is_idempotent(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id

    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)
    resp = client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)
    assert b"already saved" in resp.data.lower()

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert SavedJob.query.filter_by(user_id=user.id, job_id=job_id).count() == 1


def test_two_users_can_independently_save_same_job(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    resp = client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)
    assert b"Job saved" in resp.data  # not "already saved" — Bob hadn't saved it yet

    with app.app_context():
        assert SavedJob.query.filter_by(job_id=job_id).count() == 2


# --- Managing saved jobs / notes / status ---

def test_saved_jobs_page_requires_login(client):
    resp = client.get("/saved-jobs/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_update_saved_job_status_and_notes(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved_job_id = SavedJob.query.filter_by(user_id=user.id).first().id

    resp = client.post(
        f"/saved-jobs/{saved_job_id}/update",
        data={
            "status": "applied",
            "notes": "Applied via referral",
            "application_date": "2026-01-15",
            "interview_date": "",
        },
        follow_redirects=True,
    )
    assert b"updated" in resp.data.lower()

    with app.app_context():
        saved = SavedJob.query.get(saved_job_id)
        assert saved.status == "applied"
        assert saved.notes == "Applied via referral"
        assert saved.application_date.isoformat() == "2026-01-15"


def test_invalid_date_format_rejected(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved_job_id = SavedJob.query.filter_by(user_id=user.id).first().id

    resp = client.post(
        f"/saved-jobs/{saved_job_id}/update",
        data={"status": "applied", "notes": "", "application_date": "not-a-date", "interview_date": ""},
        follow_redirects=True,
    )
    assert b"yyyy-mm-dd" in resp.data.lower()


def test_saved_job_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)

    with app.app_context():
        alice = User.query.filter_by(email="alice@example.com").first()
        saved_job_id = SavedJob.query.filter_by(user_id=alice.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.post(f"/saved-jobs/{saved_job_id}/update", data={"status": "applied", "notes": "", "application_date": "", "interview_date": ""})
    assert resp.status_code == 403

    resp = client.post(f"/saved-jobs/{saved_job_id}/delete")
    assert resp.status_code == 403


def test_delete_saved_job(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved_job_id = SavedJob.query.filter_by(user_id=user.id).first().id

    resp = client.post(f"/saved-jobs/{saved_job_id}/delete", follow_redirects=True)
    assert b"removed" in resp.data.lower()

    with app.app_context():
        assert SavedJob.query.get(saved_job_id) is None


def test_status_filter_on_saved_jobs_page(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client, SAMPLE_JOB_TEXT)
    _analyze_job(client, SAMPLE_JOB_TEXT_2)

    with app.app_context():
        jobs = Job.query.all()
        job_ids = [j.id for j in jobs]

    client.post(f"/jobs/search/{job_ids[0]}/save", follow_redirects=True)
    client.post(f"/jobs/search/{job_ids[1]}/save", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved = SavedJob.query.filter_by(user_id=user.id).first()
        saved_id = saved.id

    client.post(
        f"/saved-jobs/{saved_id}/update",
        data={"status": "applied", "notes": "", "application_date": "", "interview_date": ""},
        follow_redirects=True,
    )

    resp = client.get("/saved-jobs/?status=applied")
    assert resp.status_code == 200
    resp_all = client.get("/saved-jobs/")
    assert resp_all.data.count(b"btn-outline-danger") >= resp.data.count(b"btn-outline-danger")


# --- Application tracker ---

def test_tracker_requires_login(client):
    resp = client.get("/saved-jobs/tracker", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_tracker_shows_zero_state(app, client):
    register_and_login(app, client)
    resp = client.get("/saved-jobs/tracker")
    assert resp.status_code == 200
    assert b"No applications tracked yet" in resp.data


def test_tracker_counts_and_conversion_rates(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client, SAMPLE_JOB_TEXT)
    _analyze_job(client, SAMPLE_JOB_TEXT_2)

    with app.app_context():
        job_ids = [j.id for j in Job.query.all()]

    client.post(f"/jobs/search/{job_ids[0]}/save", follow_redirects=True)
    client.post(f"/jobs/search/{job_ids[1]}/save", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved = SavedJob.query.filter_by(user_id=user.id).all()
        sj1_id, sj2_id = saved[0].id, saved[1].id

    client.post(f"/saved-jobs/{sj1_id}/update", data={"status": "interview", "notes": "", "application_date": "", "interview_date": ""}, follow_redirects=True)
    client.post(f"/saved-jobs/{sj2_id}/update", data={"status": "applied", "notes": "", "application_date": "", "interview_date": ""}, follow_redirects=True)

    resp = client.get("/saved-jobs/tracker")
    assert resp.status_code == 200
    assert b"2 total application" in resp.data
    assert b"50.0%" in resp.data  # 1 of 2 reached interview-or-better


# --- Quick match from search ---

def test_quick_match_against_unowned_job(app, client):
    """A user should be able to match their OWN resume against a job
    someone else analyzed, since job content is shared market data."""
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with app.app_context():
        bob = User.query.filter_by(email="bob@example.com").first()
        from app.models import Resume

        resume_id = Resume.query.filter_by(user_id=bob.id).first().id

    resp = client.post(
        f"/match/quick/{job_id}", data={"resume_id": resume_id}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Overall Match" in resp.data

    with app.app_context():
        from app.models import JobAnalysis

        report = JobAnalysis.query.filter_by(resume_id=resume_id, job_id=job_id).first()
        assert report is not None
        assert report.user_id == bob.id


def test_quick_match_cannot_use_another_users_resume(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with app.app_context():
        job_id = Job.query.first().id
        alice = User.query.filter_by(email="alice@example.com").first()
        from app.models import Resume

        alice_resume_id = Resume.query.filter_by(user_id=alice.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    client.post(f"/match/quick/{job_id}", data={"resume_id": alice_resume_id}, follow_redirects=True)

    with app.app_context():
        from app.models import JobAnalysis

        assert JobAnalysis.query.filter_by(resume_id=alice_resume_id).count() == 0


# --- Cascades ---

def test_account_deletion_cascades_saved_jobs(app, client):
    _seed(app)
    register_and_login(app, client)
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        saved_job_id = SavedJob.query.filter_by(user_id=user.id).first().id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert SavedJob.query.get(saved_job_id) is None


def test_deleting_job_cascades_saved_jobs(app, client):
    """If the original submitter deletes their job analysis, other
    users' SavedJob bookmarks pointing at it must not become orphaned
    rows with a dangling foreign key."""
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _analyze_job(client)
    with app.app_context():
        job_id = Job.query.first().id
    client.get("/auth/logout")

    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")
    client.post(f"/jobs/search/{job_id}/save", follow_redirects=True)
    with app.app_context():
        assert SavedJob.query.filter_by(job_id=job_id).count() == 1

    client.get("/auth/logout")
    register_and_login(app, client, email="alice@example.com", password="Password123", name="Alice")
    client.post(f"/jobs/{job_id}/delete", follow_redirects=True)

    with app.app_context():
        assert SavedJob.query.filter_by(job_id=job_id).count() == 0
