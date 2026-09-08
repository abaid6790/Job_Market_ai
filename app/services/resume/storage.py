"""
Secure resume file storage.

Validates both the extension AND the actual file signature (magic bytes) so
a renamed .exe can't slip through as ".pdf". Files are saved under a
per-user directory with a random filename — never the user-supplied
filename — so there's no path-traversal surface and no cross-user
filename collisions.
"""
import os
import secrets

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # keep in sync with config.MAX_CONTENT_LENGTH

_PDF_MAGIC = b"%PDF-"
_DOCX_MAGIC = b"PK\x03\x04"  # DOCX is a zip archive


class FileValidationError(Exception):
    pass


def get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_extension(filename: str) -> str:
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f'Unsupported file type ".{ext}". Please upload a PDF, DOCX, or TXT file.'
        )
    return ext


def validate_signature(file_bytes: bytes, ext: str) -> None:
    """Confirm the file's actual content matches its claimed extension."""
    if ext == "pdf":
        if not file_bytes.startswith(_PDF_MAGIC):
            raise FileValidationError("This file doesn't look like a valid PDF.")
    elif ext == "docx":
        if not file_bytes.startswith(_DOCX_MAGIC):
            raise FileValidationError("This file doesn't look like a valid DOCX.")
    elif ext == "txt":
        # Reject files with null bytes / binary content masquerading as .txt.
        if b"\x00" in file_bytes[:4096]:
            raise FileValidationError("This file doesn't look like a plain text file.")


def save_resume_file(upload_folder: str, user_id: int, filename: str, file_bytes: bytes) -> dict:
    """Validate and persist an uploaded resume. Returns storage metadata."""
    if len(file_bytes) == 0:
        raise FileValidationError("The uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileValidationError("File is too large (max 10 MB).")

    ext = validate_extension(filename)
    validate_signature(file_bytes, ext)

    user_dir = os.path.join(upload_folder, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)

    stored_filename = f"{secrets.token_hex(16)}.{ext}"
    full_path = os.path.join(user_dir, stored_filename)

    with open(full_path, "wb") as fh:
        fh.write(file_bytes)

    return {
        "stored_filename": stored_filename,
        "file_path": full_path,
        "file_type": ext,
        "file_size_bytes": len(file_bytes),
    }


def delete_resume_file(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass  # best-effort cleanup; DB row deletion is the source of truth
