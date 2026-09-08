"""
Job description parsing pipeline.

Text (pasted or extracted from an uploaded file) -> cleaning -> section
detection -> field extraction (title/company/location/remote/employment
type/salary/experience/education) -> skill extraction (required vs
preferred) -> structured DB rows.

Reuses app.services.resume.cleaner (text cleaning is not resume-specific)
and app.services.resume.skill_extractor (the taxonomy matching built in
Phase 3) rather than duplicating either — job postings and resumes need
the exact same skill-matching logic.
"""
from datetime import datetime

from app.extensions import db
from app.models import Job, JobSection, JobSkill
from app.services.resume.cleaner import clean_text
from app.services.resume.skill_extractor import extract_skills
from app.services.job.section_detector import detect_sections
from app.services.job.field_extractor import (
    extract_title_company_location,
    extract_remote_status,
    extract_employment_type,
    extract_salary,
    extract_experience_requirement,
    extract_education_requirement,
)


def process_job(job: Job, raw_text: str) -> None:
    """Parse job posting text and populate the Job's structured fields.

    Sets job.status to "completed" or "failed" and always commits.
    """
    job.status = "processing"
    db.session.commit()

    try:
        text = clean_text(raw_text)
        if not text:
            raise ValueError("The job description text is empty.")

        sections = detect_sections(text)
        job.raw_text = text

        # --- Title / company / location ---
        header_fields = extract_title_company_location(sections.get("header", ""), text)
        job.title = header_fields["title"]
        job.company = header_fields["company"]
        job.location = header_fields["location"]

        # --- Remote status / employment type ---
        job.remote_status = extract_remote_status(text)
        job.employment_type = extract_employment_type(text)

        # --- Salary ---
        salary_source = sections.get("compensation") or sections.get("benefits") or text
        salary = extract_salary(salary_source)
        job.salary_min = salary["min"]
        job.salary_max = salary["max"]
        job.salary_currency = salary["currency"]
        job.salary_period = salary["period"]

        # --- Experience requirement ---
        requirement_source = sections.get("requirements") or text
        experience = extract_experience_requirement(requirement_source)
        job.experience_years_min = experience["min"]
        job.experience_years_max = experience["max"]

        # --- Education requirement ---
        education = extract_education_requirement(requirement_source)
        job.education_level = education["level"]
        job.education_requirement_text = education["text"]

        # --- Sections ---
        for order_index, (section_type, content) in enumerate(sections.items()):
            if section_type == "header":
                continue
            db.session.add(
                JobSection(
                    job_id=job.id,
                    section_type=section_type,
                    content=content,
                    order_index=order_index,
                )
            )

        # --- Skills: required vs preferred ---
        required_source = sections.get("requirements") or text
        preferred_source = sections.get("preferred") or ""

        required_matches = extract_skills(required_source)
        preferred_matches = extract_skills(preferred_source) if preferred_source else []

        required_skill_ids = set()
        for match in required_matches:
            db.session.add(
                JobSkill(
                    job_id=job.id,
                    skill_id=match["skill_id"],
                    requirement_level="required",
                    raw_text=match["raw_text"],
                )
            )
            required_skill_ids.add(match["skill_id"])

        for match in preferred_matches:
            if match["skill_id"] in required_skill_ids:
                continue  # already captured as required — required wins
            db.session.add(
                JobSkill(
                    job_id=job.id,
                    skill_id=match["skill_id"],
                    requirement_level="preferred",
                    raw_text=match["raw_text"],
                )
            )
            required_skill_ids.add(match["skill_id"])  # dedupe within preferred too

        job.status = "completed"
        job.error_message = None

    except Exception as exc:  # noqa: BLE001 - job parsing must never 500 the request
        job.status = "failed"
        job.error_message = str(exc) if isinstance(exc, ValueError) else (
            "An unexpected error occurred while parsing this job description."
        )

    job.processed_at = datetime.utcnow()
    db.session.commit()
