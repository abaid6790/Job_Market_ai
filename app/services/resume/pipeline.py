"""
Resume parsing pipeline.

Resume -> text extraction -> cleaning -> section detection -> entity/skill/
experience/education extraction -> structured DB rows.

Runs synchronously (fine at this stage/scale). If upload volume grows,
swap the call site in the resume route for a background job — this
function's signature (resume_id in, DB rows out) doesn't need to change.
"""
from datetime import datetime

from app.extensions import db
from app.models import (
    Resume,
    ResumeSection,
    ResumeExperience,
    ResumeEducation,
    ResumeSkill,
    UserSkill,
)
from app.services.resume.extractor import extract_text, ExtractionError
from app.services.resume.cleaner import clean_text
from app.services.resume.section_detector import detect_sections
from app.services.resume.entity_extractor import extract_contact_info
from app.services.resume.skill_extractor import extract_skills
from app.services.resume.experience_extractor import extract_experience
from app.services.resume.education_extractor import extract_education


def process_resume(resume: Resume, file_path: str) -> None:
    """Parse a resume file and populate its structured DB rows in place.

    Sets resume.status to "completed" or "failed" and always commits,
    so callers don't need their own try/except around this.
    """
    resume.status = "processing"
    db.session.commit()

    try:
        raw = extract_text(file_path, resume.file_type)
        text = clean_text(raw)
        sections = detect_sections(text)

        contact = extract_contact_info(sections.get("header", ""), text)
        resume.extracted_name = contact["name"]
        resume.extracted_email = contact["email"]
        resume.extracted_phone = contact["phone"]
        resume.linkedin_url = contact["linkedin_url"]
        resume.github_url = contact["github_url"]
        resume.portfolio_url = contact["portfolio_url"]
        resume.raw_text = text

        # --- Sections ---
        for order_index, (section_type, content) in enumerate(sections.items()):
            if section_type == "header":
                continue
            db.session.add(
                ResumeSection(
                    resume_id=resume.id,
                    section_type=section_type,
                    content=content,
                    order_index=order_index,
                )
            )

        # --- Experience ---
        experience_text = sections.get("experience", "")
        for entry in extract_experience(experience_text):
            db.session.add(ResumeExperience(resume_id=resume.id, **entry))

        # --- Education ---
        education_text = sections.get("education", "")
        for entry in extract_education(education_text):
            db.session.add(ResumeEducation(resume_id=resume.id, **entry))

        # --- Skills ---
        # Scan the skills section if present, but fall back to (and also
        # always include) the full document, since skills are frequently
        # mentioned inside experience bullet points too.
        skill_matches = extract_skills(text)
        existing_user_skill_ids = {
            us.skill_id
            for us in UserSkill.query.filter_by(user_id=resume.user_id).all()
        }
        for match in skill_matches:
            db.session.add(
                ResumeSkill(
                    resume_id=resume.id,
                    skill_id=match["skill_id"],
                    raw_text=match["raw_text"],
                )
            )
            # Auto-populate the user's profile skills from the resume,
            # without ever overwriting a skill they already manage manually.
            if match["skill_id"] not in existing_user_skill_ids:
                db.session.add(
                    UserSkill(
                        user_id=resume.user_id,
                        skill_id=match["skill_id"],
                        source="resume",
                    )
                )
                existing_user_skill_ids.add(match["skill_id"])

        resume.status = "completed"
        resume.error_message = None

    except ExtractionError as exc:
        resume.status = "failed"
        resume.error_message = str(exc)
    except Exception as exc:  # noqa: BLE001 - resume parsing must never 500 the request
        resume.status = "failed"
        resume.error_message = "An unexpected error occurred while parsing this resume."

    resume.processed_at = datetime.utcnow()
    db.session.commit()
