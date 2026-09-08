"""
Skill extraction from free-form resume text.

Matches known taxonomy skill names and aliases against the text using a
single compiled regex pass (built from the current taxonomy), rather than
per-phrase scanning or an LLM call — the taxonomy is finite and this is
exact, fast, and fully auditable. Unmatched/novel skills are handled at the
UI layer (profile page) where a user can add them manually and they become
user-suggested taxonomy entries; the automated resume pass only reports
confident matches.
"""
import re

from app.models.skill import Skill, SkillAlias
from app.services.skills.normalizer import normalize_text


def _build_phrase_map() -> dict:
    """normalized phrase -> skill_id, covering canonical names + aliases."""
    phrase_map = {}
    for skill in Skill.query.filter_by(is_active=True).all():
        phrase_map[skill.normalized_name] = skill.id
    for alias in SkillAlias.query.all():
        phrase_map.setdefault(alias.normalized_alias, alias.skill_id)
    return phrase_map


def _compile_pattern(phrases):
    # Longest phrases first so multi-word skills win over any accidental
    # single-word substring overlap.
    ordered = sorted(phrases, key=len, reverse=True)
    escaped = [re.escape(p) for p in ordered if p]
    if not escaped:
        return None
    # Non-alphanumeric lookaround (rather than \b) so skills containing
    # punctuation like "C++", "C#", ".NET", "Node.js" still match correctly.
    pattern = r"(?<![A-Za-z0-9])(" + "|".join(escaped) + r")(?![A-Za-z0-9])"
    return re.compile(pattern, re.IGNORECASE)


def extract_skills(text: str) -> list[dict]:
    """Return a list of {"skill_id": int, "raw_text": str} for each distinct
    taxonomy skill found in the text (deduplicated, first-match wins)."""
    if not text:
        return []

    phrase_map = _build_phrase_map()
    pattern = _compile_pattern(phrase_map.keys())
    if pattern is None:
        return []

    normalized_full = normalize_text(text)
    found = {}  # skill_id -> raw_text (first match)

    for match in pattern.finditer(normalized_full):
        phrase = match.group(0)
        skill_id = phrase_map.get(phrase)
        if skill_id is not None and skill_id not in found:
            found[skill_id] = phrase

    return [{"skill_id": skill_id, "raw_text": raw} for skill_id, raw in found.items()]
