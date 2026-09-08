import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login_at = db.Column(db.DateTime, nullable=True)

    # --- Password handling ---
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # --- Flask-Login required property ---
    # UserMixin already provides is_active via get_id/is_authenticated etc.,
    # but we override is_active so disabled accounts can't log in even with
    # a valid session/remember-me cookie.
    @property
    def is_active(self):
        return self.is_active_account

    def __repr__(self):
        return f"<User {self.email}>"


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref(
            "email_tokens", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    @classmethod
    def create_for_user(cls, user, expiry_hours: int):
        token = secrets.token_urlsafe(48)
        record = cls(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours),
        )
        db.session.add(record)
        return record

    @property
    def is_valid(self) -> bool:
        return (not self.used) and datetime.utcnow() < self.expires_at


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref(
            "reset_tokens", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    @classmethod
    def create_for_user(cls, user, expiry_minutes: int):
        token = secrets.token_urlsafe(48)
        record = cls(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        )
        db.session.add(record)
        return record

    @property
    def is_valid(self) -> bool:
        return (not self.used) and datetime.utcnow() < self.expires_at
