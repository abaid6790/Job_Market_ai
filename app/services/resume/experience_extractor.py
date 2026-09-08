"""
Best-effort structured extraction of experience entries.

Resume formatting varies enormously, so this heuristic parser optimizes for
"never crash, never silently drop content" over "always perfectly split
title/company/dates." The full section text is always stored separately
(ResumeSection) as the source of truth, so a user can always see exactly
what was on their resume even if a specific entry's fields are guessed
imperfectly.
"""
import re

_DATE_RANGE_RE = re.compile(
    r"(?P<start>[A-Za-z]{3,9}\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4})"
    r"\s*(?:-|–|—|to)\s*"
    r"(?P<end>[A-Za-z]{3,9}\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4}|[Pp]resent|[Cc]urrent)",
)


def _split_blocks(section_text: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", section_text.strip())
    return [b.strip() for b in blocks if b.strip()]


def _extract_dates(block: str):
    match = _DATE_RANGE_RE.search(block)
    if not match:
        return None, None, False
    start = match.group("start").strip()
    end = match.group("end").strip()
    is_current = end.lower() in ("present", "current")
    return start, end, is_current


def _split_title_company(first_line: str):
    line = _DATE_RANGE_RE.sub("", first_line).strip(" -\u2013\u2014|,")
    if not line:
        return None, None

    for sep in (" at ", " @ "):
        if sep in line:
            title, company = line.split(sep, 1)
            return title.strip(), company.strip()

    if "|" in line:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]

    if "," in line:
        title, company = line.split(",", 1)
        return title.strip(), company.strip()

    if " - " in line or " \u2013 " in line:
        sep = " - " if " - " in line else " \u2013 "
        title, company = line.split(sep, 1)
        return title.strip(), company.strip()

    # Couldn't confidently split — keep the whole line as the title so
    # nothing is lost, and leave company for the user to fill in/correct.
    return line, None


def extract_experience(section_text: str) -> list[dict]:
    if not section_text:
        return []

    entries = []
    for idx, block in enumerate(_split_blocks(section_text)):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        first_line = lines[0]
        start_date, end_date, is_current = _extract_dates(block)
        title, company = _split_title_company(first_line)

        # Drop the date line itself from the description body (it's fully
        # captured in start_date/end_date already) — otherwise it leaks
        # into the free-text description as noise.
        description_lines = []
        for line in lines[1:]:
            remainder = _DATE_RANGE_RE.sub("", line).strip(" -\u2013\u2014|,")
            if remainder:
                description_lines.append(line)
        description = "\n".join(description_lines).strip() or None

        entries.append(
            {
                "job_title": title,
                "company": company,
                "location": None,
                "start_date": start_date,
                "end_date": end_date,
                "is_current": is_current,
                "description": description,
                "order_index": idx,
            }
        )

    return entries
