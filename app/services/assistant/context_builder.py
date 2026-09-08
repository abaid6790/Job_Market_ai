"""
Context builder for the AI Career Assistant — the "RAG-style retrieval"
the roadmap calls for.

This deliberately isn't vector-embedding retrieval over a document store:
each user's own data (profile, skills, resumes, analyzed jobs, match
reports, saved jobs) is small and already fully structured in the
database, so a direct, capped structured summary is the cheapest
suitable method (same philosophy as the rest of this app's NLP choices)
and is more auditable than similarity search over embeddings would be
here. If this ever needs to scale to searching across a much larger
shared corpus (e.g. all market jobs), vector retrieval would be the
right upgrade — but not for "here's what one user's data looks like."

The system prompt built here explicitly instructs the model to answer
ONLY from the provided data and to say so when something isn't covered,
rather than inventing specifics about the user's resume/jobs.
"""
from app.models import UserSkill, Resume, Job, JobAnalysis, SavedJob

MAX_SKILLS = 25
MAX_RECENT_JOBS = 5
MAX_RECENT_MATCHES = 5
MAX_GAPS_PER_MATCH = 5
JOB_TEXT_TRUNCATE = 1500


def _profile_section(user):
    profile = user.profile
    if not profile:
        return "Profile: not filled in yet."

    parts = []
    if profile.current_role:
        parts.append(f"current role: {profile.current_role}")
    if profile.target_role:
        parts.append(f"target role: {profile.target_role}")
    if profile.years_experience is not None:
        parts.append(f"{profile.years_experience} years of experience")
    if profile.education_level:
        parts.append(f"education: {profile.education_level}")
    if profile.location:
        parts.append(f"location: {profile.location}")
    if profile.remote_preference:
        parts.append(f"remote preference: {profile.remote_preference}")

    return "Profile: " + ("; ".join(parts) if parts else "no details filled in yet.")


def _skills_section(user):
    skills = (
        UserSkill.query.filter_by(user_id=user.id)
        .join(UserSkill.skill)
        .limit(MAX_SKILLS)
        .all()
    )
    if not skills:
        return "Skills: none recorded yet."
    names = [us.skill.name for us in skills]
    return f"Skills ({len(names)}): " + ", ".join(names)


def _resume_section(user):
    primary = Resume.query.filter_by(user_id=user.id, is_primary=True).first()
    if not primary:
        return "Resume: none uploaded yet."
    if primary.status != "completed":
        return f"Resume: uploaded but not yet fully processed (status: {primary.status})."

    experience_count = primary.experiences.count()
    education_count = primary.education_entries.count()
    skill_count = primary.resume_skills.count()
    return (
        f"Primary resume: {primary.original_filename} — "
        f"{experience_count} experience entr{'y' if experience_count == 1 else 'ies'}, "
        f"{education_count} education entr{'y' if education_count == 1 else 'ies'}, "
        f"{skill_count} skills detected."
    )


def _recent_job_analyses_section(user):
    jobs = (
        Job.query.filter_by(user_id=user.id, status="completed")
        .order_by(Job.created_at.desc())
        .limit(MAX_RECENT_JOBS)
        .all()
    )
    if not jobs:
        return "Recently analyzed jobs: none yet."

    lines = []
    for job in jobs:
        required = [js.skill.name for js in job.job_skills.filter_by(requirement_level="required").limit(6)]
        lines.append(
            f"- \"{job.title or 'Untitled'}\" at {job.company or 'unknown company'}"
            f"{' (' + job.location + ')' if job.location else ''}: "
            f"required skills: {', '.join(required) if required else 'none detected'}"
        )
    return "Recently analyzed jobs:\n" + "\n".join(lines)


def _recent_match_reports_section(user):
    reports = (
        JobAnalysis.query.filter_by(user_id=user.id)
        .order_by(JobAnalysis.updated_at.desc())
        .limit(MAX_RECENT_MATCHES)
        .all()
    )
    if not reports:
        return "Resume-job match reports: none yet."

    lines = []
    for report in reports:
        score_text = f"{report.overall_score}%" if report.overall_score is not None else "insufficient data"
        critical = [
            g.skill.name
            for g in report.skill_gaps.filter_by(gap_category="critical").limit(MAX_GAPS_PER_MATCH)
        ]
        lines.append(
            f"- Match against \"{report.job.title or 'Untitled'}\": overall {score_text}"
            f"{'; missing required skills: ' + ', '.join(critical) if critical else ''}"
        )
    return "Resume-job match reports:\n" + "\n".join(lines)


def _saved_jobs_section(user):
    saved = SavedJob.query.filter_by(user_id=user.id).all()
    if not saved:
        return "Saved jobs / applications: none yet."
    counts = {}
    for sj in saved:
        counts[sj.status] = counts.get(sj.status, 0) + 1
    summary = ", ".join(f"{count} {status}" for status, count in counts.items())
    return f"Saved jobs / applications: {summary}."


def _specific_job_section(job):
    if job is None:
        return ""
    required = [js.skill.name for js in job.job_skills.filter_by(requirement_level="required")]
    preferred = [js.skill.name for js in job.job_skills.filter_by(requirement_level="preferred")]
    salary = ""
    if job.salary_min:
        salary = f"{job.salary_currency or ''}{job.salary_min:,}"
        if job.salary_max and job.salary_max != job.salary_min:
            salary += f"-{job.salary_currency or ''}{job.salary_max:,}"
        if job.salary_period:
            salary += f" / {job.salary_period}"

    text = (job.raw_text or "")[:JOB_TEXT_TRUNCATE]

    return (
        f"\nThe user is specifically asking about this job posting:\n"
        f"Title: {job.title or 'Untitled'}\n"
        f"Company: {job.company or 'Unknown'}\n"
        f"Location: {job.location or 'Not specified'}\n"
        f"Remote status: {job.remote_status}\n"
        f"Salary: {salary or 'Not detected'}\n"
        f"Experience required: {job.experience_years_min or 'Not detected'}\n"
        f"Required skills: {', '.join(required) if required else 'None detected'}\n"
        f"Preferred skills: {', '.join(preferred) if preferred else 'None detected'}\n"
        f"Full description (may be truncated):\n{text}\n"
    )


def build_user_context(user, specific_job=None):
    """Returns (context_text, short_note_for_transparency_logging)."""
    sections = [
        _profile_section(user),
        _skills_section(user),
        _resume_section(user),
        _recent_job_analyses_section(user),
        _recent_match_reports_section(user),
        _saved_jobs_section(user),
    ]
    note_parts = ["profile", "skills", "resume", "job analyses", "match reports", "saved jobs"]

    if specific_job is not None:
        sections.append(_specific_job_section(specific_job))
        note_parts.append(f"job #{specific_job.id}")

    context_text = "\n\n".join(s for s in sections if s)
    note = "Context included: " + ", ".join(note_parts)
    return context_text, note


SYSTEM_PROMPT_TEMPLATE = """You are the AI Career Assistant for JobMarket AI, a job market intelligence platform.

Answer the user's question using ONLY the data provided below about them. \
Do not invent specifics about their resume, skills, jobs, or match scores \
that aren't in this data. If the data doesn't cover what they're asking, \
say so plainly and suggest what they could do in the app to get a better \
answer (e.g. "upload a resume", "analyze a job description", "run a match report") \
rather than guessing.

Keep answers concise and practical. Remind the user, when relevant, that \
match scores and recommendations are estimates, not guarantees.

--- USER DATA ---
{context}
--- END USER DATA ---
"""


def build_system_prompt(user, specific_job=None):
    context_text, note = build_user_context(user, specific_job=specific_job)
    return SYSTEM_PROMPT_TEMPLATE.format(context=context_text), note
