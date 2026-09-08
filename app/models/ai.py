from datetime import datetime

from app.extensions import db


class AIUsage(db.Model):
    """One row per AI provider call attempt (success or failure), for the
    usage statistics and cost/latency visibility the spec asks for."""

    __tablename__ = "ai_usage"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    provider = db.Column(db.String(30), nullable=False)
    model = db.Column(db.String(100), nullable=True)
    method = db.Column(db.String(20), nullable=False)  # generate | generate_json | embed | stream

    prompt_tokens = db.Column(db.Integer, nullable=True)
    completion_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)

    response_time_ms = db.Column(db.Integer, nullable=True)
    success = db.Column(db.Boolean, nullable=False)
    cache_hit = db.Column(db.Boolean, default=False, nullable=False)
    error_message = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", backref=db.backref("ai_usage", lazy="dynamic"))


class AICacheEntry(db.Model):
    """Deterministic cache of (provider, model, method, prompt) -> response,
    so repeated identical requests don't re-hit a paid API. Keyed
    per-provider-and-model per the spec, since a fallback to a different
    provider shouldn't silently serve a cached answer from another one."""

    __tablename__ = "ai_cache_entries"

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(128), unique=True, nullable=False, index=True)

    provider = db.Column(db.String(30), nullable=False)
    model = db.Column(db.String(100), nullable=True)
    response_text = db.Column(db.Text, nullable=False)
    response_meta = db.Column(db.Text, nullable=True)  # JSON-encoded token counts etc.

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    @property
    def is_valid(self) -> bool:
        return datetime.utcnow() < self.expires_at
