"""
Report data gathering.

Every function here collects data that already exists in the database —
computed by earlier phases (resume parsing, matching, roadmap
generation, market analytics). This module never computes anything new;
it only assembles a plain dict ready for export, so the exported report
can never disagree with what the user already sees on-screen elsewhere
in the app.
"""
from app.services.market import analytics as market_analytics


def gather_resume_report(resume):
    return {
        "report_type": "Resume Analysis",
        "generated_for": resume.original_filename,
        "contact": {
            "name": resume.extracted_name,
            "email": resume.extracted_email,
            "phone": resume.extracted_phone,
            "linkedin": resume.linkedin_url,
            "github": resume.github_url,
        },
        "skills": [rs.skill.name for rs in resume.resume_skills.all()],
        "experience": [
            {
                "title": e.job_title,
                "company": e.company,
                "start_date": e.start_date,
                "end_date": e.end_date,
                "is_current": e.is_current,
            }
            for e in resume.experiences.all()
        ],
        "education": [
            {
                "institution": ed.institution,
                "degree": ed.degree,
                "start_date": ed.start_date,
                "end_date": ed.end_date,
            }
            for ed in resume.education_entries.all()
        ],
    }


def gather_match_report(job_analysis):
    return {
        "report_type": "Resume-Job Match Report",
        "resume": job_analysis.resume.original_filename,
        "job_title": job_analysis.job.title,
        "company": job_analysis.job.company,
        "scores": {
            "overall": job_analysis.overall_score,
            "skills": job_analysis.skills_score,
            "experience": job_analysis.experience_score,
            "education": job_analysis.education_score,
            "keyword_coverage": job_analysis.keyword_coverage_score,
            "semantic_similarity": job_analysis.semantic_similarity_score,
        },
        "skill_gaps": {
            category: [g.skill.name for g in job_analysis.skill_gaps.filter_by(gap_category=category)]
            for category in ("critical", "important", "optional")
        },
        "disclaimer": "Match scores are estimates, not a guarantee of employment.",
    }


def gather_skill_gap_report(user):
    from app.services.roadmap.gap_aggregator import gather_gap_skills

    gap_skills = gather_gap_skills(user)
    return {
        "report_type": "Skill Gap Report",
        "gaps": [{"skill": skill.name, "category": category} for skill, category in gap_skills],
    }


def gather_roadmap_report(roadmap):
    return {
        "report_type": "Career Roadmap",
        "target_role": roadmap.target_role,
        "based_on_match_count": roadmap.based_on_match_count,
        "months": [
            {
                "month": rs.month_number,
                "skill": rs.skill.name,
                "priority": rs.source_gap_category,
                "status": rs.status,
            }
            for rs in roadmap.roadmap_skills.all()
        ],
    }


def gather_market_report():
    total = market_analytics.total_jobs_analyzed()
    return {
        "report_type": "Market Analysis Snapshot",
        "total_jobs_analyzed": total,
        "top_skills": [
            {"skill": d["skill"].name, "percentage": d["percentage"], "count": d["count"]}
            for d in market_analytics.skill_demand(limit=15)
        ],
        "top_titles": market_analytics.top_titles(limit=10),
        "remote_distribution": market_analytics.remote_distribution(),
        "salary": market_analytics.salary_stats(),
    }
