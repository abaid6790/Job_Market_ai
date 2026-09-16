"""
Multi-resume comparison.

Lets a user compare their own resume versions side by side — skill
coverage, parsed section/experience completeness, and (optionally)
scores against a specific job, reusing Phase 6's real scoring engine
rather than inventing a second comparison metric.

Strictly scoped to the requesting user's own resumes; callers must
enforce ownership before passing resumes in.
"""
from app.services.matching.engine import compute_match


def compare_resumes(user, resumes, job=None):
    if len(resumes) < 2:
        return {
            "available": False,
            "reason": "Select at least two processed resumes to compare.",
        }

    rows = []
    all_skill_names = set()

    for resume in resumes:
        skill_names = {rs.skill.name for rs in resume.resume_skills.all()}
        all_skill_names |= skill_names

        entry = {
            "resume": resume,
            "skills": sorted(skill_names),
            "skill_count": len(skill_names),
            "experience_count": resume.experiences.count(),
            "education_count": resume.education_entries.count(),
            "section_count": resume.sections.count(),
            "scores": None,
        }

        if job is not None:
            match = compute_match(user, resume, job)
            entry["scores"] = {
                "overall": match["overall"],
                "skills": match["skills"],
                "keyword": match["keyword"],
                "semantic": match["semantic"],
            }

        rows.append(entry)

    # Which skills are unique to one resume vs. shared by all — the most
    # actionable part of a version-to-version comparison.
    skill_sets = [set(r["skills"]) for r in rows]
    shared = set.intersection(*skill_sets) if skill_sets else set()
    for index, row in enumerate(rows):
        others = set().union(*(skill_sets[:index] + skill_sets[index + 1 :])) if len(skill_sets) > 1 else set()
        row["unique_skills"] = sorted(skill_sets[index] - others)

    best_overall = None
    if job is not None:
        scored = [r for r in rows if r["scores"] and r["scores"]["overall"] is not None]
        if scored:
            best_overall = max(scored, key=lambda r: r["scores"]["overall"])["resume"].id

    return {
        "available": True,
        "rows": rows,
        "shared_skills": sorted(shared),
        "job": job,
        "best_overall_resume_id": best_overall,
        "disclaimer": (
            "Comparison reflects what was parsed from each file. A lower score may mean "
            "content didn't parse cleanly rather than that the experience is weaker."
        ),
    }
