"""
Raw text extraction from uploaded resume files.

Deliberately minimal: this layer's only job is bytes-on-disk -> plain text.
All cleaning/structuring happens downstream in cleaner.py and
section_detector.py, so extraction failures are isolated and easy to
diagnose (e.g. an encrypted/scanned PDF yields empty text rather than a
mysteriously broken parse).
"""
from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError


class ExtractionError(Exception):
    """Raised when a file's text cannot be extracted at all."""


def extract_text(file_path: str, file_type: str) -> str:
    file_type = file_type.lower()
    if file_type == "pdf":
        return _extract_pdf(file_path)
    if file_type == "docx":
        return _extract_docx(file_path)
    if file_type == "txt":
        return _extract_txt(file_path)
    raise ExtractionError(f"Unsupported file type: {file_type}")


def _extract_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
    except PdfReadError as exc:
        raise ExtractionError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ExtractionError("PDF is password-protected.") from exc

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            # Skip unreadable pages rather than failing the whole document.
            continue

    text = "\n".join(pages_text).strip()
    if not text:
        raise ExtractionError(
            "No extractable text found (this can happen with scanned/image-only PDFs)."
        )
    return text


def _extract_docx(file_path: str) -> str:
    try:
        document = Document(file_path)
    except Exception as exc:
        raise ExtractionError(f"Could not read DOCX: {exc}") from exc

    parts = [p.text for p in document.paragraphs if p.text.strip()]

    # Also pull text out of tables (common in resume templates).
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)

    text = "\n".join(parts).strip()
    if not text:
        raise ExtractionError("No extractable text found in the DOCX file.")
    return text


def _extract_txt(file_path: str) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as fh:
                text = fh.read().strip()
                if text:
                    return text
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Could not decode the text file (unsupported encoding or empty file).")
