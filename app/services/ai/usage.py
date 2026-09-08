from app.extensions import db
from app.models import AIUsage


def log_usage(
    *,
    provider,
    method,
    success,
    model=None,
    user_id=None,
    prompt_tokens=None,
    completion_tokens=None,
    total_tokens=None,
    response_time_ms=None,
    cache_hit=False,
    error_message=None,
):
    entry = AIUsage(
        user_id=user_id,
        provider=provider,
        model=model,
        method=method,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        response_time_ms=response_time_ms,
        success=success,
        cache_hit=cache_hit,
        error_message=(error_message[:500] if error_message else None),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def usage_stats():
    """Aggregate usage stats for the admin AI status page."""
    total = AIUsage.query.count()
    if total == 0:
        return {"available": False}

    successes = AIUsage.query.filter_by(success=True).count()
    cache_hits = AIUsage.query.filter_by(cache_hit=True).count()

    response_times = [
        row[0] for row in db.session.query(AIUsage.response_time_ms).filter(
            AIUsage.response_time_ms.isnot(None)
        ).all()
    ]
    avg_response_time = round(sum(response_times) / len(response_times)) if response_times else None

    by_provider = {}
    rows = (
        db.session.query(AIUsage.provider, AIUsage.success, db.func.count())
        .group_by(AIUsage.provider, AIUsage.success)
        .all()
    )
    for provider, success, count in rows:
        entry = by_provider.setdefault(provider, {"success": 0, "failure": 0})
        entry["success" if success else "failure"] += count

    return {
        "available": True,
        "total_requests": total,
        "success_rate": round((successes / total) * 100, 1),
        "cache_hit_rate": round((cache_hits / total) * 100, 1),
        "avg_response_time_ms": avg_response_time,
        "by_provider": by_provider,
    }
