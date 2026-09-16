from datetime import datetime

from app.extensions import db

# Security-relevant event categories. Deliberately coarse — the point is
# an auditable trail of WHO did WHAT, not a general-purpose analytics log.
EVENT_CATEGORIES = ["auth", "admin", "data", "security"]


class ActivityLog(db.Model):
    """Append-only audit trail of security-relevant events.

    Per the spec's logging rules, this NEVER stores passwords, API keys,
    or sensitive personal content — only the actor, the action, and a
    short non-sensitive description. Rows deliberately survive user
    deletion (user_id is nullable with no cascade) so an audit trail
    can't be erased by deleting the account that created it.
    """

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = db.Column(db.String(255), nullable=True)  # denormalized so it survives deletion

    category = db.Column(db.String(20), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
