"""
Skill gap classification.

- critical: required by the job, missing from the user's skills
- important: preferred by the job, missing from the user's skills
- optional: not explicitly listed by this job posting, but frequently
  required alongside skills this job DOES want (market-wide, from Phase
  5's co-occurrence data) — genuinely useful "you might also want to
  learn X" suggestions, grounded in actual collected data rather than
  invented. If the market dataset is too small to support any pairs
  above the threshold, this list is simply empty — no fallback guessing.
"""
from collections import Counter

from app.services.market.analytics import skill_cooccurrence

MIN_COOCCURRENCE_FOR_OPTIONAL = 2
MAX_OPTIONAL_SUGGESTIONS = 5


def compute_skill_gaps(required_ids: set, preferred_ids: set, user_skill_ids: set) -> dict:
    critical = required_ids - user_skill_ids
    important = (preferred_ids - user_skill_ids) - critical

    already_covered = critical | important | user_skill_ids
    job_relevant_ids = required_ids | preferred_ids

    optional_scores = Counter()
    for pair in skill_cooccurrence(limit=500):
        if pair["count"] < MIN_COOCCURRENCE_FOR_OPTIONAL:
            continue
        a_id, b_id = pair["skill_a"].id, pair["skill_b"].id
        if a_id in job_relevant_ids and b_id not in already_covered:
            optional_scores[b_id] += pair["count"]
        elif b_id in job_relevant_ids and a_id not in already_covered:
            optional_scores[a_id] += pair["count"]

    optional = {skill_id for skill_id, _ in optional_scores.most_common(MAX_OPTIONAL_SUGGESTIONS)}

    return {"critical": critical, "important": important, "optional": optional}
