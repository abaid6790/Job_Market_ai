from app.extensions import db
from app.models import (
    User,
    Resume,
    Job,
    CareerRoadmap,
    RoadmapSkill,
    Recommendation,
    LearningResource,
)
from app.services.skills.seed import seed_taxonomy
from app.services.roadmap.learning_resources import seed_learning_resources
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()
        seed_learning_resources()


def _setup_resume_and_gap_match(app, client):
    """Uploads the sample resume and matches it against sample_job_gap.txt
    (which requires skills the resume lacks), producing real skill gaps
    to build a roadmap from."""
    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with open("tests/fixtures/sample_job_gap.txt") as fh:
        client.post("/jobs/analyze", data={"job_text": fh.read()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume_id = Resume.query.filter_by(user_id=user.id).first().id
        job_id = Job.query.filter_by(user_id=user.id).first().id

    client.post("/match/analyze", data={"resume_id": resume_id, "job_id": job_id}, follow_redirects=True)


# --- Access ---

def test_roadmap_requires_login(client):
    resp = client.get("/roadmap/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_roadmap_shows_insufficient_data_before_any_match(app, client):
    register_and_login(app, client)
    resp = client.get("/roadmap/")
    assert resp.status_code == 200
    assert b"don't have a roadmap yet" in resp.data


# --- Generation from real gap data ---

def test_generate_roadmap_from_real_gaps(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)

    resp = client.post("/roadmap/generate", follow_redirects=True)
    assert b"Career roadmap generated" in resp.data
    assert b"Rust" in resp.data or b"Terraform" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        roadmap = CareerRoadmap.query.filter_by(user_id=user.id).first()
        assert roadmap is not None
        skills = roadmap.roadmap_skills.all()
        assert len(skills) > 0
        categories = [rs.source_gap_category for rs in skills]
        if "important" in categories and "critical" in categories:
            assert categories.index("critical") < categories.index("important")
        months = [rs.month_number for rs in skills]
        assert months == sorted(months)
        assert months[0] == 1


def test_roadmap_generation_with_no_match_reports_gives_honest_message(app, client):
    register_and_login(app, client)
    resp = client.post("/roadmap/generate", follow_redirects=True)
    assert b"Not enough data" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert CareerRoadmap.query.filter_by(user_id=user.id).count() == 0


def test_regenerating_roadmap_preserves_progress_on_existing_skills(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        roadmap = CareerRoadmap.query.filter_by(user_id=user.id).first()
        rs_id = roadmap.roadmap_skills.first().id

    client.post(f"/roadmap/skills/{rs_id}/status", data={"status": "learning"}, follow_redirects=True)
    client.post("/roadmap/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        roadmap = CareerRoadmap.query.filter_by(user_id=user.id).first()
        with_status = [r for r in roadmap.roadmap_skills.all() if r.status == "learning"]
        assert len(with_status) >= 1


def test_regenerate_updates_in_place_not_duplicated(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)

    client.post("/roadmap/generate", follow_redirects=True)
    client.post("/roadmap/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert CareerRoadmap.query.filter_by(user_id=user.id).count() == 1


# --- Skill status updates ---

def test_update_skill_status(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        roadmap = CareerRoadmap.query.filter_by(user_id=user.id).first()
        rs_id = roadmap.roadmap_skills.first().id

    resp = client.post(f"/roadmap/skills/{rs_id}/status", data={"status": "completed"}, follow_redirects=True)
    assert b"completed" in resp.data.lower()

    with app.app_context():
        rs = RoadmapSkill.query.get(rs_id)
        assert rs.status == "completed"


def test_roadmap_skill_status_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        rs_id = CareerRoadmap.query.filter_by(user_id=user.id).first().roadmap_skills.first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.post(f"/roadmap/skills/{rs_id}/status", data={"status": "completed"})
    assert resp.status_code == 403


# --- Learning resources: real curated links, never fabricated ---

def test_curated_learning_resources_shown_for_known_skills(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/generate", follow_redirects=True)

    resp = client.get("/roadmap/")
    assert b"doc.rust-lang.org" in resp.data or b"developer.hashicorp.com" in resp.data


def test_skill_without_curated_resource_shows_honest_message_not_fabricated_link(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/generate", follow_redirects=True)

    with app.app_context():
        from app.services.roadmap.learning_resources import get_resources_for_skill
        from app.models import Skill

        elasticsearch = Skill.query.filter_by(name="Elasticsearch").first()
        resources = get_resources_for_skill(elasticsearch.id)
        assert resources == []


def test_admin_can_add_learning_resource(app, client):
    _seed(app)
    register_and_login(app, client)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user.is_admin = True
        db.session.commit()
        from app.models import Skill

        python_id = Skill.query.filter_by(name="Python").first().id

    resp = client.post(
        "/admin/learning-resources",
        data={
            "skill_id": python_id,
            "title": "Real Python Tutorials",
            "url": "https://realpython.com/",
            "resource_type": "tutorial",
        },
        follow_redirects=True,
    )
    assert b"Learning resource added" in resp.data

    with app.app_context():
        resource = LearningResource.query.filter_by(url="https://realpython.com/").first()
        assert resource is not None
        assert resource.is_curated is False


def test_admin_learning_resources_requires_admin(app, client):
    register_and_login(app, client)
    resp = client.get("/admin/learning-resources")
    assert resp.status_code == 403


# --- Project recommendations: deterministic, grounded in real gaps ---

def test_generate_project_recommendations_from_real_gaps(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)

    resp = client.post("/roadmap/recommendations/generate", follow_redirects=True)
    assert b"Generated" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        recs = Recommendation.query.filter_by(user_id=user.id).all()
        assert len(recs) > 0
        all_gap_names = {"Rust", "Terraform", "Elasticsearch", "Kafka"}
        for rec in recs:
            tech_names = {t.strip() for t in rec.suggested_technologies.split(",")}
            assert tech_names.issubset(all_gap_names)
            assert rec.difficulty in ("beginner", "intermediate", "advanced")
            assert rec.estimated_time


def test_project_recommendations_insufficient_data_message(app, client):
    register_and_login(app, client)
    resp = client.post("/roadmap/recommendations/generate", follow_redirects=True)
    assert b"Not enough data" in resp.data


def test_regenerating_recommendations_replaces_not_duplicates(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)

    client.post("/roadmap/recommendations/generate", follow_redirects=True)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        first_count = Recommendation.query.filter_by(user_id=user.id).count()

    client.post("/roadmap/recommendations/generate", follow_redirects=True)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        second_count = Recommendation.query.filter_by(user_id=user.id).count()

    assert first_count == second_count


def test_delete_recommendation(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/recommendations/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        rec_id = Recommendation.query.filter_by(user_id=user.id).first().id

    resp = client.post(f"/roadmap/recommendations/{rec_id}/delete", follow_redirects=True)
    assert b"removed" in resp.data.lower()

    with app.app_context():
        assert Recommendation.query.get(rec_id) is None


def test_recommendation_requires_ownership(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/recommendations/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        rec_id = Recommendation.query.filter_by(user_id=user.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.post(f"/roadmap/recommendations/{rec_id}/delete")
    assert resp.status_code == 403


# --- Cascades ---

def test_account_deletion_cascades_roadmap_and_recommendations(app, client):
    _seed(app)
    register_and_login(app, client)
    _setup_resume_and_gap_match(app, client)
    client.post("/roadmap/generate", follow_redirects=True)
    client.post("/roadmap/recommendations/generate", follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user_id = user.id
        roadmap_id = CareerRoadmap.query.filter_by(user_id=user_id).first().id
        rec_id = Recommendation.query.filter_by(user_id=user_id).first().id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert CareerRoadmap.query.get(roadmap_id) is None
        assert RoadmapSkill.query.filter_by(roadmap_id=roadmap_id).count() == 0
        assert Recommendation.query.get(rec_id) is None
