"""Clean raw extracted text before section detection / entity extraction."""
import re

_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_BULLET_RE = re.compile(r"^[\s]*[•●▪◦‣∙·–-]\s*", re.MULTILINE)
_NON_PRINTABLE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_text(raw: str) -> str:
    if not raw:
        return ""

    text = _NON_PRINTABLE_RE.sub("", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Normalize common bullet characters to a plain "- " so downstream
    # section/entry splitting has one consistent bullet marker to look for.
    text = _BULLET_RE.sub("- ", text)

    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)

    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    return text
