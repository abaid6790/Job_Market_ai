"""Best-effort structured extraction of education entries. Same philosophy
as experience_extractor.py: never crash, never drop content, degrade to
storing the whole line rather than guessing wrong with confidence."""
import re

from app.services.resume.experience_extractor import _DATE_RANGE_RE, _split_blocks

_DEGREE_KEYWORDS = [
    "bachelor", "master", "phd", "doctorate", "associate", "b.sc", "m.sc",
    "b.a.", "m.a.", "b.tech", "m.tech", "mba", "bs ", "ms ", "ba ", "ma ",
]


def _split_institution_degree(first_line: str):
    line = _DATE_RANGE_RE.sub("", first_line).strip(" -\u2013\u2014|,")
    if not line:
        return None, None

    lowered = line.lower()
    has_degree_keyword = any(kw in lowered for kw in _DEGREE_KEYWORDS)

    if "," in line:
        left, right = line.split(",", 1)
        left, right = left.strip(), right.strip()
        # Whichever side reads like a degree, keep that as degree.
        if any(kw in left.lower() for kw in _DEGREE_KEYWORDS):
            return right, left  # institution, degree
        return left, right  # institution, degree

    if has_degree_keyword:
        return None, line  # only a degree line, institution likely on another line

    return line, None  # only an institution line


def extract_education(section_text: str) -> list[dict]:
    if not section_text:
        return []

    entries = []
    for idx, block in enumerate(_split_blocks(section_text)):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        first_line = lines[0]
        match = _DATE_RANGE_RE.search(block)
        start_date = match.group("start").strip() if match else None
        end_date = match.group("end").strip() if match else None

        institution, degree = _split_institution_degree(first_line)

        # If institution wasn't found on line 1, check line 2.
        if institution is None and len(lines) > 1:
            second_line = _DATE_RANGE_RE.sub("", lines[1]).strip(" -\u2013\u2014|,")
            if second_line:
                institution = second_line

        entries.append(
            {
                "institution": institution,
                "degree": degree,
                "field_of_study": None,
                "start_date": start_date,
                "end_date": end_date,
                "order_index": idx,
            }
        )

    return entries
