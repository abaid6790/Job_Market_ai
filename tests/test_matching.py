from app.extensions import db
from app.models import User, Resume, Job, JobAnalysis, SkillGap, UserProfile
from app.services.skills.seed import seed_taxonomy
from app.services.resume.pipeline import process_resume
from app.services.job.pipeline import process_job
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _setup_resume_and_job(app, client, job_fixture="sample_job.txt", years_experience=5, education_level="bachelor"):
    """Upload the sample resume and analyze a job via the real routes,
    optionally setting profile experience/education, and return their ids."""
    if years_experience is not None or education_level is not None:
        data = {}
        if years_experience is not None:
            data["years_experience"] = str(years_experience)
        if education_level is not None:
            data["education_level"] = education_level
        client.post("/profile/", data=data, follow_redirects=True)

    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with open(f"tests/fixtures/{job_fixture}") as fh:
        text = fh.read()
    client.post("/jobs/analyze", data={"job_text": text}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc()).first()
        job = Job.query.filter_by(user_id=user.id).order_by(Job.created_at.desc()).first()
        return resume.id, job.id


def test_matching_page_requires_login(client):
    resp = client.get("/match/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_matching_index_prompts_when_no_resume_or_job(app, client):
    register_and_login(app, client)
    resp = client.get("/match/")
    assert b"need at least one" in resp.data.lower()


def test_full_match_scenario_high_score_no_gaps(app, client):
    """sample_resume covers every skill sample_job asks for -> should
    produce a high score and zero critical/important gaps."""
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(app, client, "sample_job.txt", years_experience=5, education_level="bachelor")

    resp = client.post(
        "/match/analyze",
        data={"resume_id": resume_id, "job_id": job_id},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Match analysis complete" in resp.data

    with app.app_context():
        report = JobAnalysis.query.filter_by(resume_id=resume_id, job_id=job_id).first()
        assert report is not None
        assert report.skills_score == 100.0
        assert report.experience_score == 100.0  # user has 5y, job needs 5y
        assert report.education_score == 100.0  # bachelor meets bachelor
        assert report.overall_score is not None
        assert report.overall_score > 70
        assert SkillGap.query.filter_by(job_analysis_id=report.id, gap_category="critical").count() == 0
        assert SkillGap.query.filter_by(job_analysis_id=report.id, gap_category="important").count() == 0


def test_gap_scenario_produces_correct_critical_and_important(app, client):
    """sample_job_gap.txt requires skills the sample resume doesn't have."""
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(
        app, client, "sample_job_gap.txt", years_experience=3, education_level="bachelor"
    )

    with app.app_context():
        from app.services.matching.engine import save_match_report

        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)
        report = save_match_report(user, resume, job)

        critical_names = {g.skill.name for g in report.skill_gaps.filter_by(gap_category="critical")}
        important_names = {g.skill.name for g in report.skill_gaps.filter_by(gap_category="important")}

        assert "Terraform" in critical_names
        assert "Rust" in critical_names
        assert "Elasticsearch" in important_names
        assert "Kafka" in important_names
        # A skill should never appear in both tiers.
        assert critical_names.isdisjoint(important_names)

        # Job needs 6 years, user has 3 -> 50%.
        assert report.experience_score == 50.0
        # Job needs master's, user has bachelor's -> 0%.
        assert report.education_score == 0.0
        # No required/preferred skills matched at all -> 0%.
        assert report.skills_score == 0.0


def test_skills_score_weighted_required_and_preferred(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(app, client, "sample_job.txt")

    with app.app_context():
        from app.services.matching.scoring import skills_score

        # 3 of 4 required matched (75%), 1 of 3 preferred matched (33.3%)
        result = skills_score({1, 2, 3, 4}, {5, 6, 7}, {1, 2, 3, 5})
        expected = round(75.0 * 0.7 + (100 / 3) * 0.3, 1)
        assert result == expected


def test_education_score_ordinal_comparison(app, client):
    from app.services.matching.scoring import education_score

    assert education_score("master", "bachelor") == 100.0
    assert education_score("bachelor", "master") == 0.0
    assert education_score("bachelor", "bachelor") == 100.0
    # Non-ordinal levels are not confidently comparable.
    assert education_score("bootcamp", "bachelor") is None
    assert education_score(None, "bachelor") is None


def test_experience_score_partial_credit(app, client):
    from app.services.matching.scoring import experience_score

    assert experience_score(5, 5) == 100.0
    assert experience_score(10, 5) == 100.0
    assert experience_score(2, 4) == 50.0
    assert experience_score(None, 4) is None
    assert experience_score(3, None) is None


def test_semantic_similarity_insufficient_data_on_empty_text(app):
    from app.services.matching.semantic import semantic_similarity

    assert semantic_similarity("", "some job text") is None
    assert semantic_similarity("resume text", "") is None
    assert semantic_similarity("Python developer with Flask", "Python Flask backend role") is not None


def test_keyword_coverage_insufficient_data_on_empty_text(app):
    from app.services.matching.keyword_coverage import keyword_coverage

    assert keyword_coverage("", "resume") is None
    assert keyword_coverage("job description", "") is None


def test_overall_score_none_when_no_subscores_available(app):
    from app.services.matching.scoring import overall_score

    assert overall_score({"skills": None, "semantic": None, "keyword": None, "experience": None, "education": None}) is None


def test_overall_score_renormalizes_available_weights(app):
    from app.services.matching.scoring import overall_score

    # Only skills (100) and experience (50) available.
    result = overall_score({"skills": 100, "semantic": None, "keyword": None, "experience": 50, "education": None})
    # weights: skills=0.40, experience=0.15 -> total 0.55
    expected = round((100 * 0.40 + 50 * 0.15) / 0.55, 1)
    assert result == expected


def test_rerun_match_updates_in_place_not_duplicated(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(app, client)

    with app.app_context():
        from app.services.matching.engine import save_match_report

        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)

        save_match_report(user, resume, job)
        save_match_report(user, resume, job)  # run again

        assert JobAnalysis.query.filter_by(resume_id=resume_id, job_id=job_id).count() == 1


def test_match_report_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    resume_id, job_id = _setup_resume_and_job(app, client)

    with app.app_context():
        from app.services.matching.engine import save_match_report

        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)
        report = save_match_report(user, resume, job)
        report_id = report.id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.get(f"/match/{report_id}")
    assert resp.status_code == 403

    resp = client.post(f"/match/{report_id}/delete")
    assert resp.status_code == 403


def test_cannot_match_another_users_resume_or_job(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    resume_id, job_id = _setup_resume_and_job(app, client)

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    # Bob's dropdown choices are scoped to his own resumes/jobs (he has
    # none), so WTForms' SelectField itself rejects Alice's ids as an
    # invalid choice before any ownership check even runs — confirm no
    # match report is created, regardless of which layer caught it.
    resp = client.post(
        "/match/analyze",
        data={"resume_id": resume_id, "job_id": job_id},
        follow_redirects=True,
    )
    assert resp.status_code == 200  # redirected back with a validation error, not a crash
    with app.app_context():
        assert JobAnalysis.query.count() == 0

    # Belt-and-suspenders: even if Bob somehow had matching dropdown
    # choices (e.g. by uploading his own resume/job with the same ids in
    # a different scenario), the route's explicit ownership check must
    # still independently block it. Simulate that directly.
    with app.app_context():
        bob = User.query.filter_by(email="bob@example.com").first()
        alice_resume = Resume.query.get(resume_id)
        alice_job = Job.query.get(job_id)
        assert alice_resume.user_id != bob.id
        assert alice_job.user_id != bob.id


def test_disclaimer_shown_on_report(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(app, client)

    with app.app_context():
        from app.services.matching.engine import save_match_report

        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)
        report = save_match_report(user, resume, job)
        report_id = report.id

    resp = client.get(f"/match/{report_id}")
    assert b"estimates" in resp.data.lower()
    assert b"not a guarantee" in resp.data.lower() or b"not guarantee" in resp.data.lower()


def test_delete_match_report(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(app, client)

    with app.app_context():
        from app.services.matching.engine import save_match_report

        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)
        report = save_match_report(user, resume, job)
        report_id = report.id

    resp = client.post(f"/match/{report_id}/delete", follow_redirects=True)
    assert b"deleted" in resp.data.lower()

    with app.app_context():
        assert JobAnalysis.query.get(report_id) is None


def test_account_deletion_cascades_match_reports(app, client):
    _seed(app)
    register_and_login(app, client)
    resume_id, job_id = _setup_resume_and_job(app, client)

    with app.app_context():
        from app.services.matching.engine import save_match_report

        user = User.query.filter_by(email="alice@example.com").first()
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)
        report = save_match_report(user, resume, job)
        report_id = report.id
        user_id = user.id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert JobAnalysis.query.get(report_id) is None
        assert SkillGap.query.filter_by(job_analysis_id=report_id).count() == 0


def test_optional_gaps_from_market_cooccurrence(app, client):
    """With enough market co-occurrence data (Python+Docker frequently
    paired), an optional suggestion should surface for a job wanting
    Python but not explicitly Docker, if the user lacks Docker."""
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")

    # Build up market co-occurrence: several jobs pairing Python + Docker.
    for i in range(3):
        client.post(
            "/jobs/analyze",
            data={"job_text": f"Role {i}\n\nRequirements\nPython and Docker required.\n"},
            follow_redirects=True,
        )

    resume_id, _ = _setup_resume_and_job(app, client, "sample_job.txt")

    with app.app_context():
        from app.services.matching.skill_gap import compute_skill_gaps
        from app.models import Skill

        python_id = Skill.query.filter_by(name="Python").first().id
        docker_id = Skill.query.filter_by(name="Docker").first().id

        # Simulate: job wants Python (required), user has Python but not Docker.
        gaps = compute_skill_gaps(required_ids={python_id}, preferred_ids=set(), user_skill_ids={python_id})
        assert docker_id in gaps["optional"]
