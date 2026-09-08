from datetime import datetime

from app.extensions import db

MESSAGE_ROLES = ["user", "assistant"]


class AIConversation(db.Model):
    __tablename__ = "ai_conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship(
        "User", backref=db.backref("ai_conversations", lazy="dynamic", cascade="all, delete-orphan")
    )
    messages = db.relationship(
        "AIMessage",
        backref="conversation",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="AIMessage.id",
    )


class AIMessage(db.Model):
    __tablename__ = "ai_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("ai_conversations.id"), nullable=False, index=True
    )
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)

    # A short, human-readable note of what grounding data was included
    # when generating this reply (e.g. "profile, 3 skills, job #12") —
    # kept for transparency, not shown as raw JSON to the user.
    context_note = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
