"""
Skill normalization and lookup.

This is intentionally conservative: normalization only lowercases, trims,
and collapses whitespace/punctuation. Mapping known variants (e.g.
"ReactJS" -> "React", "Postgres" -> "PostgreSQL") is done through explicit
SkillAlias rows rather than aggressive regex guessing, so matches stay
predictable and auditable — this is the same normalizer Phase 3 (resume
parsing) and Phase 4 (job description parsing) will reuse.
"""
import re

from app.extensions import db
from app.models.skill import Skill, SkillAlias

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s+#.]")  # keep +, #, . for C++, C#, Node.js, etc.


def normalize_text(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip().lower()
    text = _PUNCT_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def find_skill(raw_name: str) -> Skill | None:
    """Look up a canonical Skill by exact normalized name or known alias."""
    normalized = normalize_text(raw_name)
    if not normalized:
        return None

    skill = Skill.query.filter_by(normalized_name=normalized, is_active=True).first()
    if skill:
        return skill

    alias = SkillAlias.query.filter_by(normalized_alias=normalized).first()
    if alias and alias.skill.is_active:
        return alias.skill

    return None


def get_or_suggest_skill(raw_name: str) -> Skill:
    """Find a matching taxonomy skill, or create a new user-suggested one.

    User-suggested skills have no category and are flagged for admin
    triage, so the taxonomy grows without ever blocking a user's input or
    requiring a code change.
    """
    existing = find_skill(raw_name)
    if existing:
        return existing

    normalized = normalize_text(raw_name)
    display_name = raw_name.strip()

    skill = Skill(
        name=display_name,
        normalized_name=normalized,
        category_id=None,
        is_user_suggested=True,
        is_active=True,
    )
    db.session.add(skill)
    db.session.flush()  # get skill.id without a full commit
    return skill


def search_skills(query: str, limit: int = 10):
    """Simple prefix/substring search over active skill names, for autocomplete."""
    normalized = normalize_text(query)
    if not normalized:
        return []
    return (
        Skill.query.filter(
            Skill.is_active.is_(True),
            Skill.normalized_name.like(f"%{normalized}%"),
        )
        .order_by(Skill.is_user_suggested.asc(), Skill.name.asc())
        .limit(limit)
        .all()
    )
