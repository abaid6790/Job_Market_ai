"""
Keyword coverage — a distinct, simpler metric from semantic similarity.

Extracts the job posting's significant terms (excluding stopwords) and
measures what fraction appear verbatim in the resume text. This is the
classic ATS-style check: it catches exact terminology matches (tool
names, methodologies, phrases) that a bag-of-words semantic similarity
score can under-weight, and it's simple enough to explain to a user
plainly, which matters for a score they'll see and act on.
"""
import re
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
_DEFAULT_KEYWORD_LIMIT = 30


def _extract_keywords(text: str, limit: int = _DEFAULT_KEYWORD_LIMIT) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    words = [w for w in words if w not in ENGLISH_STOP_WORDS]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]


def keyword_coverage(job_text: str, resume_text: str) -> float | None:
    if not job_text or not job_text.strip() or not resume_text or not resume_text.strip():
        return None

    keywords = _extract_keywords(job_text)
    if not keywords:
        return None

    resume_lower = resume_text.lower()
    found = sum(1 for kw in keywords if kw in resume_lower)
    return round((found / len(keywords)) * 100, 1)
