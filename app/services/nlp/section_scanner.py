"""
Generic "split text into named sections by header line" scanner.

Both resumes and job postings are dominated by a predictable, small
vocabulary of section headers on their own line (EXPERIENCE, REQUIREMENTS,
etc.) — this shared scanner takes a synonym map and does the header
detection + splitting once, so resume and job section detectors are thin
synonym-list wrappers around the same logic instead of duplicated code.
"""
import re

_MAX_HEADER_LEN = 50


def _normalize_header(line: str) -> str:
    text = line.strip().strip(":").strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def _looks_like_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADER_LEN:
        return False
    if stripped.endswith((".", ",")):
        return False
    letters = [c for c in stripped if c.isalpha()]
    if not letters:
        return False
    is_upper = stripped.upper() == stripped
    is_title = stripped.istitle()
    return is_upper or is_title


def scan_sections(text: str, synonym_map: dict) -> dict:
    """Split text into sections using a {canonical_type: [synonyms]} map.

    Returns {section_type: content}. Text before the first recognized
    header is returned under "header".
    """
    header_lookup = {
        synonym: section_type
        for section_type, synonyms in synonym_map.items()
        for synonym in synonyms
    }

    lines = text.split("\n")
    boundaries = []

    for idx, line in enumerate(lines):
        if not _looks_like_header(line):
            continue
        normalized = _normalize_header(line)
        section_type = header_lookup.get(normalized)
        if section_type:
            boundaries.append((idx, section_type))

    sections = {}
    if not boundaries:
        sections["other"] = text.strip()
        return sections

    preamble = "\n".join(lines[: boundaries[0][0]]).strip()
    if preamble:
        sections["header"] = preamble

    for i, (start_idx, section_type) in enumerate(boundaries):
        end_idx = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
        content = "\n".join(lines[start_idx + 1 : end_idx]).strip()
        if not content:
            continue
        if section_type in sections:
            sections[section_type] += "\n\n" + content
        else:
            sections[section_type] = content

    return sections
