"""
Audit logging.

Deliberately narrow: this records WHO did WHAT, never the content of what
they did. The `description` field is for short, non-sensitive context
("disabled user #12", "imported 40 jobs") — never resume text, never a
password, never an API key. `_SENSITIVE_PATTERNS` is a defensive backstop
that redacts anything that looks like a secret even if a future caller
passes one in by mistake.
"""
import logging
import re

from flask import request, has_request_context
from flask_login import current_user

from app.extensions import db
from app.models import ActivityLog

logger = logging.getLogger("jobmarket_ai.audit")

_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token|authorization)\s*[=:]\s*\S+"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bBearer\s+\S+"),
]

_REDACTED = "[REDACTED]"


def _redact(text):
    if not text:
        return text
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text[:500]


def _client_ip():
    if not has_request_context():
        return None
    # X-Forwarded-For is only meaningful behind a trusted proxy; take the
    # first hop if present, otherwise the direct peer.
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.remote_addr or "")[:45] or None


def log_event(category, action, description=None, user=None):
    """Record a security-relevant event. Never raises — an audit write
    failing must not break the user-facing request that triggered it."""
    try:
        actor = user
        if actor is None and has_request_context():
            try:
                actor = current_user if current_user.is_authenticated else None
            except Exception:
                actor = None

        entry = ActivityLog(
            user_id=getattr(actor, "id", None),
            user_email=getattr(actor, "email", None),
            category=category,
            action=action[:100],
            description=_redact(description),
            ip_address=_client_ip(),
        )
        db.session.add(entry)
        db.session.commit()
        logger.info("audit: %s/%s by %s", category, action, getattr(actor, "email", "anonymous"))
        return entry
    except Exception:
        db.session.rollback()
        logger.exception("Failed to write audit log entry for %s/%s", category, action)
        return None
