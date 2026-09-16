"""
Optional AI-enhanced resume improvement suggestions.

Same graceful-degradation contract as Phase 9's assistant: if no AI
provider is configured, or a call fails, this returns a clear, honest
message rather than crashing or fabricating advice. The deterministic
analysis in improvement.py is always shown regardless — this is a
qualitative layer on top, not a replacement for it.

The system prompt explicitly forbids inventing new experience,
education, certifications, or achievements — the model is only allowed
to suggest rewording/restructuring of what's already in the resume, or
point out (already-detected, real) missing keywords/skills.
"""
from app.services.ai import get_ai_manager
from app.services.ai.base import AIProviderError

NO_PROVIDER_MESSAGE = (
    "AI-enhanced suggestions aren't available right now — no AI provider is "
    "configured for this deployment. The analysis above is based on deterministic "
    "checks and doesn't require AI to be useful."
)
GENERIC_FAILURE_MESSAGE = (
    "Sorry, couldn't get AI-enhanced suggestions just now. The analysis above is "
    "still fully valid — please try again in a moment."
)

SYSTEM_PROMPT = """You are a resume improvement assistant for JobMarket AI.

Suggest concrete improvements to the resume content provided below. \
You may suggest rewording bullet points for clarity/impact, restructuring \
sections, or highlighting skills the user already has more prominently.

You must NEVER invent new experience, job titles, education, certifications, \
dates, employers, or achievements that aren't already stated in the resume \
text below. If you don't have enough information to make a specific \
suggestion, say so rather than guessing or inventing.

Keep suggestions concise, specific, and actionable — a short bulleted list, \
not a rewritten resume.
"""


def get_ai_suggestions(user, resume, deterministic_analysis, job=None):
    manager = get_ai_manager()

    context_parts = [f"RESUME TEXT:\n{resume.raw_text or '(no text extracted)'}"]

    if deterministic_analysis["missing_sections"]:
        context_parts.append(
            "Missing sections detected: " + ", ".join(deterministic_analysis["missing_sections"])
        )
    if deterministic_analysis["missing_keywords"]:
        context_parts.append(
            "Keywords from the target job not found in the resume: "
            + ", ".join(deterministic_analysis["missing_keywords"][:10])
        )
    if deterministic_analysis["missing_skills"]:
        critical = deterministic_analysis["missing_skills"].get("critical", [])
        if critical:
            context_parts.append("Required skills for the target job not found in the resume: " + ", ".join(critical))
    if job is not None:
        context_parts.append(f"Target job: {job.title or 'Untitled'} at {job.company or 'Unknown company'}")

    prompt = "\n\n".join(context_parts)

    try:
        response = manager.generate(prompt, system=SYSTEM_PROMPT, user_id=user.id, max_tokens=600)
        return {"available": True, "text": response.text}
    except AIProviderError:
        message = NO_PROVIDER_MESSAGE if not manager.configured_providers() else GENERIC_FAILURE_MESSAGE
        return {"available": False, "text": message}
