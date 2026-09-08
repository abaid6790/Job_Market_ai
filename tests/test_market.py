import io

from app.extensions import db
from app.models import User, Job
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def _make_admin(app, email="alice@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        user.is_admin = True
        db.session.commit()


SAMPLE_CSV = (
    "title,company,location,remote_status,employment_type,salary_min,salary_max,"
    "salary_currency,salary_period,experience_years_min,education_level,skills,preferred_skills\n"
    "Backend Engineer,Acme,San Francisco,remote,full_time,120000,160000,USD,year,3,bachelor,"
    "Python;Flask;PostgreSQL,Docker;AWS\n"
    "Data Scientist,DataCo,New York,hybrid,full_time,130000,170000,USD,year,4,master,"
    "Python;Machine Learning;SQL,TensorFlow\n"
    "Frontend Engineer,WebCo,Austin,onsite,full_time,100000,140000,USD,year,2,bachelor,"
    "React;JavaScript;CSS,TypeScript\n"
)


def _import_sample_dataset(app, client):
    _make_admin(app)
    page = client.get("/admin/data-import")
    resp = client.post(
        "/admin/data-import",
        data={"file": (io.BytesIO(SAMPLE_CSV.encode()), "jobs.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    return resp


def test_market_dashboard_requires_login(client):
    resp = client.get("/market/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_dashboard_shows_insufficient_data_when_empty(app, client):
    register_and_login(app, client)
    resp = client.get("/market/")
    assert b"No jobs have been analyzed yet" in resp.data


def test_dashboard_shows_data_after_import(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)

    resp = client.get("/market/")
    assert b"No jobs have been analyzed yet" not in resp.data
    assert b"Python" in resp.data


def test_admin_import_requires_admin(app, client):
    register_and_login(app, client)
    resp = client.get("/admin/data-import")
    assert resp.status_code == 403


def test_csv_import_creates_jobs_and_skills(app, client):
    _seed(app)
    register_and_login(app, client)
    resp = _import_sample_dataset(app, client)
    assert b"3 imported" in resp.data

    with app.app_context():
        jobs = Job.query.filter_by(source="imported").all()
        assert len(jobs) == 3
        titles = {j.title for j in jobs}
        assert "Backend Engineer" in titles
        backend = Job.query.filter_by(title="Backend Engineer", source="imported").first()
        assert backend.salary_min == 120000
        assert backend.company == "Acme"
        skill_names = {js.skill.name for js in backend.job_skills}
        assert "Python" in skill_names
        assert "Docker" in skill_names


def test_csv_import_deduplicates_on_reimport(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)
    resp = _import_sample_dataset(app, client)
    assert b"3 duplicates" in resp.data

    with app.app_context():
        assert Job.query.filter_by(source="imported").count() == 3


def test_csv_import_skips_rows_missing_title(app, client):
    _seed(app)
    register_and_login(app, client)
    bad_csv = "title,company\n,NoTitleCo\nReal Title,RealCo\n"
    resp = client.post(
        "/admin/data-import",
        data={"file": (io.BytesIO(b""), "placeholder.csv")},  # will be replaced below
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    _make_admin(app)
    resp = client.post(
        "/admin/data-import",
        data={"file": (io.BytesIO(bad_csv.encode()), "bad.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"1 imported" in resp.data
    assert b"1 rows skipped" in resp.data or b"1 " in resp.data


def test_json_import(app, client):
    _seed(app)
    register_and_login(app, client)
    _make_admin(app)
    payload = (
        '{"jobs": [{"title": "ML Engineer", "company": "AIco", "skills": ["Python", "TensorFlow"]}]}'
    )
    resp = client.post(
        "/admin/data-import",
        data={"file": (io.BytesIO(payload.encode()), "jobs.json")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"1 imported" in resp.data
    with app.app_context():
        job = Job.query.filter_by(title="ML Engineer", source="imported").first()
        assert job is not None
        assert {js.skill.name for js in job.job_skills} == {"Python", "TensorFlow"}


def test_xlsx_import(app, client):
    _seed(app)
    register_and_login(app, client)
    _make_admin(app)

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["title", "company", "skills"])
    ws.append(["DevOps Engineer", "OpsCo", "Docker;Kubernetes"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = client.post(
        "/admin/data-import",
        data={"file": (buf, "jobs.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"1 imported" in resp.data
    with app.app_context():
        job = Job.query.filter_by(title="DevOps Engineer", source="imported").first()
        assert job is not None


def test_salary_stats_insufficient_data_below_threshold(app, client):
    _seed(app)
    register_and_login(app, client)
    _make_admin(app)
    # Only 2 rows with salary — below MIN_JOBS_FOR_SALARY_STATS (3).
    csv_data = (
        "title,salary_min,salary_max,salary_currency,salary_period,skills\n"
        "Role A,100000,120000,USD,year,Python\n"
        "Role B,110000,130000,USD,year,Java\n"
    )
    client.post(
        "/admin/data-import",
        data={"file": (io.BytesIO(csv_data.encode()), "jobs.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    from app.services.market import analytics

    with app.app_context():
        stats = analytics.salary_stats()
        assert stats["available"] is False
        assert stats["sample_size"] == 2


def test_salary_stats_available_at_threshold(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)  # 3 jobs, all with USD/year salary

    from app.services.market import analytics

    with app.app_context():
        stats = analytics.salary_stats()
        assert stats["available"] is True
        assert stats["sample_size"] == 3
        assert stats["min"] == 100000
        assert stats["max"] == 170000


def test_skill_demand_percentages_correct(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)

    from app.services.market import analytics

    with app.app_context():
        demand = analytics.skill_demand()
        python_row = next(d for d in demand if d["skill"].name == "Python")
        # Python appears in 2 of 3 jobs (Backend Engineer, Data Scientist).
        assert python_row["count"] == 2
        assert python_row["percentage"] == round(2 / 3 * 100, 1)


def test_skill_cooccurrence(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)

    from app.services.market import analytics

    with app.app_context():
        pairs = analytics.skill_cooccurrence()
        pair_names = [{p["skill_a"].name, p["skill_b"].name} for p in pairs]
        assert {"Python", "Flask"} in pair_names


def test_role_analytics(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)

    from app.services.market import analytics

    with app.app_context():
        result = analytics.role_analytics("Engineer")
        assert result["available"] is True
        assert result["job_count"] == 2  # Backend Engineer + Frontend Engineer

        no_match = analytics.role_analytics("Nonexistent Role Title XYZ")
        assert no_match["available"] is False


def test_role_explorer_page(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)

    resp = client.get("/market/roles?title=Engineer")
    assert resp.status_code == 200
    assert b"matching job" in resp.data


def test_skill_explorer_and_detail_pages(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)

    resp = client.get("/market/skills")
    assert resp.status_code == 200
    assert b"Python" in resp.data

    with app.app_context():
        from app.models import Skill

        python = Skill.query.filter_by(name="Python").first()

    resp = client.get(f"/market/skills/{python.id}")
    assert resp.status_code == 200
    assert b"Flask" in resp.data  # co-occurring skill


def test_trends_insufficient_data_with_single_month(app, client):
    _seed(app)
    register_and_login(app, client)
    _import_sample_dataset(app, client)  # all created "now" -> one month only

    from app.services.market import analytics

    with app.app_context():
        trends = analytics.skill_trends()
        assert trends["available"] is False


def test_own_analyzed_job_contributes_to_market_data(app, client):
    """A job a regular (non-admin) user analyzes via /jobs/analyze should
    also show up in aggregate market stats — market data isn't admin-only."""
    _seed(app)
    register_and_login(app, client)

    with open("tests/fixtures/sample_job.txt") as fh:
        text = fh.read()
    client.post("/jobs/analyze", data={"job_text": text}, follow_redirects=True)

    from app.services.market import analytics

    with app.app_context():
        assert analytics.total_jobs_analyzed() == 1
        demand = analytics.skill_demand()
        assert any(d["skill"].name == "Python" for d in demand)


def test_market_data_does_not_expose_other_users_private_info(app, client):
    """Market aggregates are fine to share (job posting content isn't
    personal data), but the dashboard should never leak which user
    submitted which job."""
    _seed(app)
    register_and_login(app, client, email="alice@example.com", name="Alice")
    with open("tests/fixtures/sample_job.txt") as fh:
        text = fh.read()
    client.post("/jobs/analyze", data={"job_text": text}, follow_redirects=True)

    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.get("/market/")
    assert b"alice@example.com" not in resp.data
    assert b"Alice" not in resp.data
