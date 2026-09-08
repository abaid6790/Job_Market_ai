"""
Best-effort structured field extraction from job posting text.

Same philosophy as the resume extractors: deterministic regex/keyword
heuristics rather than an LLM call (cheapest suitable method for this
kind of task), never crash, degrade gracefully when a field can't be
confidently determined rather than guessing with false confidence — an
unmatched field is left None/"unknown" rather than fabricated.
"""
import re

_LABELED_FIELD_RE = {
    "title": re.compile(r"(?im)^\s*(?:job\s*title|title|position)\s*[:\-]\s*(.+)$"),
    "company": re.compile(r"(?im)^\s*company(?:\s*name)?\s*[:\-]\s*(.+)$"),
    "location": re.compile(r"(?im)^\s*location\s*[:\-]\s*(.+)$"),
}

_REMOTE_KEYWORDS = [
    (re.compile(r"\bremote\b", re.IGNORECASE), "remote"),
    (re.compile(r"\bhybrid\b", re.IGNORECASE), "hybrid"),
    (re.compile(r"\bon[\s-]?site\b|\bin[\s-]?office\b", re.IGNORECASE), "onsite"),
]

_EMPLOYMENT_KEYWORDS = [
    (re.compile(r"\bfull[\s-]?time\b", re.IGNORECASE), "full_time"),
    (re.compile(r"\bpart[\s-]?time\b", re.IGNORECASE), "part_time"),
    (re.compile(r"\bcontract(?:or)?\b", re.IGNORECASE), "contract"),
    (re.compile(r"\bintern(?:ship)?\b", re.IGNORECASE), "internship"),
    (re.compile(r"\btemporary\b|\btemp\b", re.IGNORECASE), "temporary"),
]

_CURRENCY_SYMBOLS = {"$": "USD", "\u00a3": "GBP", "\u20ac": "EUR"}

_SALARY_RANGE_RE = re.compile(
    r"(?P<cur1>[$\u00a3\u20ac])\s?(?P<min>\d[\d,]*\.?\d*\s?[kK]?)"
    r"\s*(?:-|\u2013|\u2014|to)\s*"
    r"(?P<cur2>[$\u00a3\u20ac])?\s?(?P<max>\d[\d,]*\.?\d*\s?[kK]?)"
)
_SALARY_SINGLE_RE = re.compile(r"(?P<cur>[$\u00a3\u20ac])\s?(?P<amount>\d[\d,]*\.?\d*\s?[kK]?)")

_PERIOD_HOUR_RE = re.compile(r"per\s*hour|/\s*hr\b|/\s*hour\b|hourly", re.IGNORECASE)
_PERIOD_MONTH_RE = re.compile(r"per\s*month|/\s*month\b|monthly", re.IGNORECASE)
_PERIOD_YEAR_RE = re.compile(r"per\s*year|/\s*year\b|/\s*yr\b|annually|per\s*annum", re.IGNORECASE)

_EXPERIENCE_RE = re.compile(
    r"(?P<min>\d{1,2})\s*(?:(?P<plus>\+)|(?:\s*(?:-|\u2013|to)\s*(?P<max>\d{1,2})))?"
    r"\+?\s*years?\s*(?:of\s+)?(?:relevant\s+|professional\s+)?experience",
    re.IGNORECASE,
)

_DEGREE_KEYWORDS = [
    ("phd", "phd"), ("doctorate", "phd"),
    ("master", "master"), ("m.sc", "master"), ("mba", "master"),
    ("bachelor", "bachelor"), ("b.sc", "bachelor"), ("b.tech", "bachelor"),
    ("associate", "associate"),
]


def _normalize_amount(raw: str) -> int:
    cleaned = raw.replace(",", "").strip()
    if cleaned.lower().endswith("k"):
        return int(float(cleaned[:-1]) * 1000)
    return int(float(cleaned))


def extract_title_company_location(header_text: str, full_text: str) -> dict:
    result = {"title": None, "company": None, "location": None}

    # Prefer explicit "Label: value" fields if the posting has them.
    for field, pattern in _LABELED_FIELD_RE.items():
        match = pattern.search(full_text)
        if match:
            result[field] = match.group(1).strip()

    if all(result.values()):
        return result

    # Fallback: the classic "Title\nCompany — Location" header layout.
    lines = [l.strip() for l in (header_text or "").split("\n") if l.strip()]
    if not lines:
        return result

    if result["title"] is None:
        result["title"] = lines[0]

    if len(lines) > 1 and (result["company"] is None or result["location"] is None):
        second_line = lines[1]
        for sep in (" \u2014 ", " - ", " | ", ", "):
            if sep in second_line:
                left, right = second_line.split(sep, 1)
                if result["company"] is None:
                    result["company"] = left.strip()
                if result["location"] is None:
                    result["location"] = right.strip()
                break
        else:
            if result["company"] is None:
                result["company"] = second_line

    return result


def extract_remote_status(text: str) -> str:
    for pattern, status in _REMOTE_KEYWORDS:
        if pattern.search(text):
            return status
    return "unknown"


def extract_employment_type(text: str) -> str:
    for pattern, emp_type in _EMPLOYMENT_KEYWORDS:
        if pattern.search(text):
            return emp_type
    return "unknown"


def extract_salary(text: str) -> dict:
    result = {"min": None, "max": None, "currency": None, "period": None}

    match = _SALARY_RANGE_RE.search(text)
    if match:
        result["currency"] = _CURRENCY_SYMBOLS.get(match.group("cur1"))
        try:
            result["min"] = _normalize_amount(match.group("min"))
            result["max"] = _normalize_amount(match.group("max"))
        except ValueError:
            result["min"] = result["max"] = None
    else:
        match = _SALARY_SINGLE_RE.search(text)
        if match:
            result["currency"] = _CURRENCY_SYMBOLS.get(match.group("cur"))
            try:
                amount = _normalize_amount(match.group("amount"))
                result["min"] = result["max"] = amount
            except ValueError:
                match = None

    if match and result["min"] is not None:
        window = text[max(0, match.start() - 10) : match.end() + 30]
        if _PERIOD_HOUR_RE.search(window):
            result["period"] = "hour"
        elif _PERIOD_MONTH_RE.search(window):
            result["period"] = "month"
        elif _PERIOD_YEAR_RE.search(window):
            result["period"] = "year"
        else:
            # No explicit period found — infer from magnitude: salaries
            # quoted under ~1000 are virtually always hourly rates.
            result["period"] = "hour" if result["max"] < 1000 else "year"

    return result


def extract_experience_requirement(text: str) -> dict:
    match = _EXPERIENCE_RE.search(text)
    if not match:
        return {"min": None, "max": None}
    min_years = int(match.group("min"))
    max_years = int(match.group("max")) if match.group("max") else None
    return {"min": min_years, "max": max_years}


def extract_education_requirement(text: str) -> dict:
    lowered = text.lower()
    for keyword, level in _DEGREE_KEYWORDS:
        idx = lowered.find(keyword)
        if idx == -1:
            continue
        line_start = lowered.rfind("\n", 0, idx) + 1
        line_end = lowered.find("\n", idx)
        if line_end == -1:
            line_end = len(text)
        snippet = text[line_start:line_end].strip(" -\u2022\u2013")
        return {"level": level, "text": snippet[:300] if snippet else None}
    return {"level": None, "text": None}
