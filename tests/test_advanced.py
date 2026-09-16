from datetime import datetime, timedelta

from app.extensions import db
from app.models import User, Job, JobSkill, Skill, Resume
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _analyze(client, text):
    return client.post("/jobs/analyze", data={"job_text": text}, follow_redirects=True)


def _job_text(title, skills):
    return f"{title}\n\nRequirements\n{' and '.join(skills)} required.\n"


def _make_jobs(client, count, skills=("Python", "Docker")):
    for i in range(count):
        _analyze(client, _job_text(f"Engineer {i}", list(skills)))


# --- Access control ---

def test_advanced_pages_require_login(client):
    for path in ("/advanced/", "/advanced/skill-graph", "/advanced/clusters", "/advanced/forecast", "/advanced/compare-resumes"):
        resp = client.get(path, follow_redirects=True)
        assert b"log in" in resp.data.lower(), f"{path} not login-gated"


def test_advanced_index_loads(app, client):
    register_and_login(app, client)
    resp = client.get("/advanced/")
    assert resp.status_code == 200
    assert b"Advanced Insights" in resp.data


# --- Skill graph: honest gating ---

def test_skill_graph_insufficient_data_with_no_jobs(app, client):
    register_and_login(app, client)
    resp = client.get("/advanced/skill-graph")
    assert resp.status_code == 200
    assert b"Insufficient data" in resp.data


def test_skill_graph_builds_from_real_cooccurrence(app, client):
    _seed(app)
    register_and_login(app, client)
    _make_jobs(client, 4, skills=("Python", "Docker"))

    with app.app_context():
        from app.services.advanced.skill_graph import build_skill_graph

        graph = build_skill_graph()
        assert graph["available"] is True
        names = {n["name"] for n in graph["nodes"]}
        assert "Python" in names and "Docker" in names
        # An edge must exist because they genuinely co-occurred.
        assert len(graph["edges"]) >= 1
        for edge in graph["edges"]:
            assert edge["weight"] >= graph["min_edge_weight"]


def test_skill_graph_reports_no_relationships_rather_than_empty_graph(app, client):
    """Skills present but never co-occurring enough must produce an
    honest message, not a graph of disconnected dots."""
    _seed(app)
    register_and_login(app, client)
    # Each job has exactly one distinct skill -> no co-occurrence at all.
    for skill in ("Python", "Java", "Rust", "Go"):
        _analyze(client, _job_text(f"{skill} Role", [skill]))

    with app.app_context():
        from app.services.advanced.skill_graph import build_skill_graph

        graph = build_skill_graph()
        assert graph["available"] is False
        assert "no real relationships" in graph["reason"].lower() or "appeared together" in graph["reason"].lower()


def test_skill_graph_json_endpoint(app, client):
    _seed(app)
    register_and_login(app, client)
    _make_jobs(client, 4)
    resp = client.get("/advanced/skill-graph.json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "available" in data


# --- Clustering ---

def test_clustering_insufficient_data(app, client):
    _seed(app)
    register_and_login(app, client)
    _make_jobs(client, 2)
    resp = client.get("/advanced/clusters")
    assert b"Insufficient data" in resp.data


def test_clustering_groups_real_jobs(app, client):
    _seed(app)
    register_and_login(app, client)
    # Two genuinely different job families.
    for i in range(4):
        _analyze(client, _job_text(f"Backend Engineer {i}", ["Python", "Docker", "PostgreSQL"]))
    for i in range(4):
        _analyze(client, _job_text(f"Frontend Engineer {i}", ["React", "JavaScript", "CSS"]))

    with app.app_context():
        from app.services.advanced.clustering import cluster_jobs

        result = cluster_jobs()
        assert result["available"] is True
        assert result["cluster_count"] >= 2
        assert sum(c["size"] for c in result["clusters"]) == result["total_jobs"]
        # Labels must be derived from the data, not empty placeholders.
        for cluster in result["clusters"]:
            assert cluster["top_terms"], "cluster has no derived label terms"


# --- Forecasting: the strictest gating ---

def test_forecast_refuses_without_enough_history(app, client):
    """A fresh deployment must NOT produce a forecast. This is the
    expected behaviour, not a failure."""
    _seed(app)
    register_and_login(app, client)
    _make_jobs(client, 10)  # plenty of jobs, but all in ONE month

    resp = client.get("/advanced/forecast")
    assert b"Insufficient data" in resp.data

    with app.app_context():
        from app.services.advanced.forecasting import forecast_skill_demand

        result = forecast_skill_demand()
        assert result["available"] is False
        assert result["months_required"] == 3
        # No projected numbers may leak into an unavailable result.
        assert "rising" not in result
        assert "falling" not in result


def test_forecast_works_with_genuine_multi_month_history(app, client):
    """Backdate jobs across several months so there IS real history."""
    _seed(app)
    register_and_login(app, client)
    _make_jobs(client, 12, skills=("Python", "Docker"))

    with app.app_context():
        jobs = Job.query.filter_by(status="completed").all()
        assert len(jobs) >= 12
        now = datetime.utcnow()
        # 4 jobs each across 3 distinct months.
        for index, job in enumerate(jobs[:12]):
            months_back = index // 4
            job.created_at = now - timedelta(days=30 * months_back + 1)
        db.session.commit()

        from app.services.advanced.forecasting import forecast_skill_demand

        result = forecast_skill_demand()
        assert result["available"] is True, result.get("reason")
        assert len(result["months_used"]) >= 3
        assert "method_note" in result
        # Every projection must carry its uncertainty band and history.
        for group in ("rising", "falling", "stable"):
            for p in result[group]:
                assert "volatility" in p
                assert "history" in p
                assert 0 <= p["projected_demand"] <= 100


def test_forecast_method_note_is_explicit_about_limitations(app):
    from app.services.advanced.forecasting import METHOD_NOTE

    lowered = METHOD_NOTE.lower()
    assert "estimate" in lowered
    assert "not a market prediction" in lowered


# --- Multi-resume comparison ---

def test_compare_requires_two_resumes(app, client):
    _seed(app)
    register_and_login(app, client)
    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "sample_resume.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    resp = client.get("/advanced/compare-resumes")
    assert b"at least two processed resumes" in resp.data


def test_compare_two_resumes(app, client):
    _seed(app)
    register_and_login(app, client)
    for name in ("v1.txt", "v2.txt"):
        with open("tests/fixtures/sample_resume.txt", "rb") as fh:
            client.post(
                "/resume/upload",
                data={"file": (fh, name)},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        ids = [r.id for r in Resume.query.filter_by(user_id=user.id).all()]

    resp = client.get(f"/advanced/compare-resumes?resume_id={ids[0]}&resume_id={ids[1]}")
    assert resp.status_code == 200
    assert b"Skills in every version" in resp.data


def test_compare_against_a_job_uses_real_scores(app, client):
    _seed(app)
    register_and_login(app, client)
    for name in ("v1.txt", "v2.txt"):
        with open("tests/fixtures/sample_resume.txt", "rb") as fh:
            client.post(
                "/resume/upload",
                data={"file": (fh, name)},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
    with open("tests/fixtures/sample_job.txt") as fh:
        client.post("/jobs/analyze", data={"job_text": fh.read()}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        resume_ids = [r.id for r in Resume.query.filter_by(user_id=user.id).all()]
        job_id = Job.query.filter_by(user_id=user.id).first().id
        resumes = Resume.query.filter(Resume.id.in_(resume_ids)).all()
        job = Job.query.get(job_id)

        from app.services.advanced.resume_comparison import compare_resumes

        result = compare_resumes(user, resumes, job)
        assert result["available"] is True
        for row in result["rows"]:
            assert row["scores"] is not None
            assert row["scores"]["overall"] is not None
        assert result["best_overall_resume_id"] in resume_ids


def test_compare_cannot_include_another_users_resume(app, client):
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    with open("tests/fixtures/sample_resume.txt", "rb") as fh:
        client.post(
            "/resume/upload",
            data={"file": (fh, "alice.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
    with app.app_context():
        alice = User.query.filter_by(email="alice@example.com").first()
        alice_resume_id = Resume.query.filter_by(user_id=alice.id).first().id

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    # Bob asks to compare Alice's resume — it must simply not appear in
    # the comparison (his own resume list is the only source).
    resp = client.get(f"/advanced/compare-resumes?resume_id={alice_resume_id}")
    assert resp.status_code == 200
    assert b"alice.txt" not in resp.data


def test_comparison_includes_parsing_disclaimer(app, client):
    _seed(app)
    register_and_login(app, client)
    for name in ("v1.txt", "v2.txt"):
        with open("tests/fixtures/sample_resume.txt", "rb") as fh:
            client.post(
                "/resume/upload",
                data={"file": (fh, name)},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        ids = [r.id for r in Resume.query.filter_by(user_id=user.id).all()]

    resp = client.get(f"/advanced/compare-resumes?resume_id={ids[0]}&resume_id={ids[1]}")
    assert b"parse cleanly" in resp.data


# --- Modularity guarantee ---

def test_advanced_features_do_not_affect_core_pages(app, client):
    """The roadmap requires these be modular and not break the core."""
    _seed(app)
    register_and_login(app, client)
    for path in ("/dashboard/", "/market/", "/resume/", "/jobs/", "/match/", "/roadmap/", "/reports/"):
        assert client.get(path).status_code == 200, f"{path} broke"
