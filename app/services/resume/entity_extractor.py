"""Structured contact-info extraction from the resume header/preamble."""
import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?:[\s.-]?\d{2,4})?"
)
_LINKEDIN_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/\S+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"(https?://)?(www\.)?github\.com/\S+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")


def _clean_url(match: str) -> str:
    url = match.rstrip(".,;)")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _guess_name(text: str) -> str | None:
    """The name is almost always the first non-empty line that isn't
    contact info — resumes are near-universally formatted this way."""
    for line in text.split("\n")[:5]:
        candidate = line.strip()
        if not candidate:
            continue
        if _EMAIL_RE.search(candidate) or _PHONE_RE.search(candidate):
            continue
        if _URL_RE.search(candidate) or "linkedin" in candidate.lower() or "github" in candidate.lower():
            continue
        # A name line is short and mostly alphabetic.
        letters = sum(c.isalpha() or c.isspace() for c in candidate)
        if len(candidate) <= 60 and letters / max(len(candidate), 1) > 0.8:
            return candidate
    return None


def extract_contact_info(header_text: str, full_text: str) -> dict:
    """Extract contact fields, searching the header first and falling back
    to the full document for links that sometimes sit in a footer."""
    search_text = header_text or full_text

    email_match = _EMAIL_RE.search(search_text) or _EMAIL_RE.search(full_text)
    phone_match = _PHONE_RE.search(search_text)

    linkedin_match = _LINKEDIN_RE.search(full_text)
    github_match = _GITHUB_RE.search(full_text)

    portfolio_url = None
    for url_match in _URL_RE.finditer(full_text):
        url = url_match.group(0)
        if "linkedin.com" in url.lower() or "github.com" in url.lower():
            continue
        portfolio_url = _clean_url(url)
        break

    return {
        "name": _guess_name(search_text),
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
        "linkedin_url": _clean_url(linkedin_match.group(0)) if linkedin_match else None,
        "github_url": _clean_url(github_match.group(0)) if github_match else None,
        "portfolio_url": portfolio_url,
    }
