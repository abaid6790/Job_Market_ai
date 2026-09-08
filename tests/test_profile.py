from app.extensions import db
from app.models import User, UserProfile, UserSkill, UserCertification, Skill, SkillCategory
from app.services.skills.seed import seed_taxonomy
from tests.helpers import register, login, verify_user, register_and_login


def _seed(app):
    with app.app_context():
        seed_taxonomy()


def test_profile_requires_login(client):
    resp = client.get("/profile/", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_profile_update_persists(app, client):
    register_and_login(app, client)

    resp = client.post(
        "/profile/",
        data={
            "location": "Faisalabad, PK",
            "current_role": "Backend Developer",
            "target_role": "ML Engineer",
            "years_experience": "3",
            "education_level": "bachelor",
            "remote_preference": "remote",
            "preferred_industries": "Fintech, Healthcare",
            "preferred_locations": "Remote, Lahore",
            "bio": "I build things.",
        },
        follow_redirects=True,
    )
    assert b"Profile updated" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        profile = UserProfile.query.filter_by(user_id=user.id).first()
        assert profile.target_role == "ML Engineer"
        assert profile.years_experience == 3
        assert profile.remote_preference == "remote"
        assert profile.preferred_industries == ["Fintech", "Healthcare"]
        assert profile.preferred_locations == ["Remote", "Lahore"]


def test_invalid_years_experience_rejected(app, client):
    register_and_login(app, client)
    resp = client.post(
        "/profile/",
        data={"years_experience": "not-a-number"},
        follow_redirects=True,
    )
    assert b"whole number" in resp.data.lower()


def test_add_skill_matches_taxonomy(app, client):
    _seed(app)
    register_and_login(app, client)

    resp = client.post(
        "/profile/skills",
        data={"skill_name": "python", "proficiency": "advanced", "years_experience": "5"},
        follow_redirects=True,
    )
    assert b"Added" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        link = UserSkill.query.filter_by(user_id=user.id).first()
        assert link is not None
        assert link.skill.name == "Python"
        assert link.skill.is_user_suggested is False
        assert link.proficiency == "advanced"
        assert link.years_experience == 5


def test_add_skill_via_known_alias(app, client):
    _seed(app)
    register_and_login(app, client)

    client.post("/profile/skills", data={"skill_name": "ReactJS"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        link = UserSkill.query.filter_by(user_id=user.id).first()
        assert link.skill.name == "React"  # resolved through the alias table


def test_add_unknown_skill_creates_user_suggested_entry(app, client):
    _seed(app)
    register_and_login(app, client)

    client.post(
        "/profile/skills", data={"skill_name": "Zylotronics Framework"}, follow_redirects=True
    )

    with app.app_context():
        skill = Skill.query.filter_by(normalized_name="zylotronics framework").first()
        assert skill is not None
        assert skill.is_user_suggested is True
        assert skill.category_id is None


def test_duplicate_skill_add_is_prevented(app, client):
    _seed(app)
    register_and_login(app, client)

    client.post("/profile/skills", data={"skill_name": "Python"}, follow_redirects=True)
    resp = client.post("/profile/skills", data={"skill_name": "python programming"}, follow_redirects=True)
    assert b"already on your profile" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert UserSkill.query.filter_by(user_id=user.id).count() == 1


def test_delete_skill_requires_ownership(app, client):
    _seed(app)
    # User A adds a skill.
    register_and_login(app, client, email="alice@example.com", name="Alice")
    client.post("/profile/skills", data={"skill_name": "Python"}, follow_redirects=True)

    with app.app_context():
        alice = User.query.filter_by(email="alice@example.com").first()
        link = UserSkill.query.filter_by(user_id=alice.id).first()
        link_id = link.id

    # Log out, register User B, try to delete Alice's skill link.
    client.get("/auth/logout")
    register_and_login(app, client, email="bob@example.com", password="Password123", name="Bob")

    resp = client.post(f"/profile/skills/{link_id}/delete", follow_redirects=True)
    assert resp.status_code == 403

    with app.app_context():
        assert UserSkill.query.get(link_id) is not None  # untouched


def test_add_and_delete_certification(app, client):
    register_and_login(app, client)

    resp = client.post(
        "/profile/certifications",
        data={"name": "AWS Certified Solutions Architect", "issuing_organization": "AWS", "year_obtained": "2024"},
        follow_redirects=True,
    )
    assert b"Certification added" in resp.data

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        cert = UserCertification.query.filter_by(user_id=user.id).first()
        assert cert.name == "AWS Certified Solutions Architect"
        cert_id = cert.id

    resp = client.post(f"/profile/certifications/{cert_id}/delete", follow_redirects=True)
    assert b"Certification removed" in resp.data


def test_deleting_account_cascades_profile_skills_certs(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/profile/", data={"target_role": "ML Engineer"}, follow_redirects=True)
    client.post("/profile/skills", data={"skill_name": "Python"}, follow_redirects=True)
    client.post(
        "/profile/certifications",
        data={"name": "PMP"},
        follow_redirects=True,
    )

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user_id = user.id

    client.post("/auth/delete-account", data={"password": "Password123"}, follow_redirects=True)

    with app.app_context():
        assert User.query.get(user_id) is None
        assert UserProfile.query.filter_by(user_id=user_id).count() == 0
        assert UserSkill.query.filter_by(user_id=user_id).count() == 0
        assert UserCertification.query.filter_by(user_id=user_id).count() == 0


def test_skill_autocomplete_api(app, client):
    _seed(app)
    register_and_login(app, client)

    resp = client.get("/api/skills/suggest?q=pyth")
    assert resp.status_code == 200
    names = [item["name"] for item in resp.get_json()]
    assert "Python" in names


def test_autocomplete_requires_login(client):
    resp = client.get("/api/skills/suggest?q=python", follow_redirects=True)
    assert b"log in" in resp.data.lower()


def test_non_admin_blocked_from_taxonomy_admin(app, client):
    register_and_login(app, client)
    resp = client.get("/admin/taxonomy")
    assert resp.status_code == 403


def test_admin_can_manage_taxonomy(app, client):
    register_and_login(app, client)
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user.is_admin = True
        db.session.commit()

    resp = client.get("/admin/taxonomy")
    assert resp.status_code == 200

    resp = client.post(
        "/admin/taxonomy/categories",
        data={"name": "Emerging Tech", "description": "New stuff"},
        follow_redirects=True,
    )
    assert b"added" in resp.data.lower()

    with app.app_context():
        category = SkillCategory.query.filter_by(name="Emerging Tech").first()
        assert category is not None
        category_id = category.id

    resp = client.post(
        "/admin/taxonomy/skills",
        data={"name": "Quantum Computing", "category_id": str(category_id)},
        follow_redirects=True,
    )
    assert b"added" in resp.data.lower()

    with app.app_context():
        skill = Skill.query.filter_by(normalized_name="quantum computing").first()
        assert skill is not None
        assert skill.category_id == category_id
        skill_id = skill.id

    resp = client.post(
        f"/admin/taxonomy/skills/{skill_id}/alias",
        data={"alias": "QC"},
        follow_redirects=True,
    )
    assert b"added" in resp.data.lower()


def test_admin_can_triage_user_suggested_skill(app, client):
    _seed(app)
    register_and_login(app, client)
    client.post("/profile/skills", data={"skill_name": "Some Brand New Tool"}, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        user.is_admin = True
        db.session.commit()
        skill = Skill.query.filter_by(normalized_name="some brand new tool").first()
        assert skill.category_id is None
        skill_id = skill.id
        category_id = SkillCategory.query.first()

    # Seed created no categories yet since we didn't call full seed with categories in this branch;
    # ensure at least one category exists to assign to.
    with app.app_context():
        if not SkillCategory.query.first():
            db.session.add(SkillCategory(name="Misc", slug="misc"))
            db.session.commit()
        category = SkillCategory.query.first()
        category_id = category.id

    resp = client.post(
        f"/admin/taxonomy/skills/{skill_id}/assign",
        data={"category_id": str(category_id)},
        follow_redirects=True,
    )
    assert b"assigned" in resp.data.lower()

    with app.app_context():
        skill = Skill.query.get(skill_id)
        assert skill.category_id == category_id
        assert skill.is_user_suggested is False
