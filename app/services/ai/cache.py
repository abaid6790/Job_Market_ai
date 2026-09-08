"""
Deterministic response cache, keyed by (provider, model, method, prompt,
system, extra context) — per the spec, provider and model are part of the
key so a fallback to a different provider never silently serves a cached
answer from another one.
"""
import hashlib
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import AICacheEntry


def build_cache_key(provider: str, model: str, method: str, prompt: str, extra: dict | None = None) -> str:
    payload = {
        "provider": provider,
        "model": model,
        "method": method,
        "prompt": prompt,
        "extra": extra or {},
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_cached(cache_key: str):
    entry = AICacheEntry.query.filter_by(cache_key=cache_key).first()
    if entry is None or not entry.is_valid:
        return None
    return entry


def set_cached(cache_key: str, *, provider: str, model: str, response_text: str, meta: dict, ttl_seconds: int) -> AICacheEntry:
    existing = AICacheEntry.query.filter_by(cache_key=cache_key).first()
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    if existing:
        existing.response_text = response_text
        existing.response_meta = json.dumps(meta)
        existing.expires_at = expires_at
        entry = existing
    else:
        entry = AICacheEntry(
            cache_key=cache_key,
            provider=provider,
            model=model,
            response_text=response_text,
            response_meta=json.dumps(meta),
            expires_at=expires_at,
        )
        db.session.add(entry)

    db.session.commit()
    return entry
