import os
from datetime import timedelta
import tempfile

basedir = os.path.abspath(os.path.dirname(__file__))


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    DEBUG = _bool(os.environ.get("DEBUG"), True)

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'jobmarket_ai.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Sessions / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(
        days=int(os.environ.get("REMEMBER_COOKIE_DAYS", 14))
    )
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # --- Email ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _bool(os.environ.get("MAIL_USE_TLS"), True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "noreply@jobmarket-ai.local"
    )

    # --- Tokens ---
    EMAIL_TOKEN_EXPIRY_HOURS = int(os.environ.get("EMAIL_TOKEN_EXPIRY_HOURS", 24))
    PASSWORD_RESET_EXPIRY_MINUTES = int(
        os.environ.get("PASSWORD_RESET_EXPIRY_MINUTES", 30)
    )

    # --- Uploads (used from Phase 3 onward) ---
    UPLOAD_FOLDER = os.path.join(basedir, "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # --- AI providers ---
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")
    AI_PROVIDER_ORDER = [
        p.strip()
        for p in os.environ.get("AI_PROVIDER_ORDER", "gemini,groq,openrouter,claude").split(",")
        if p.strip()
    ]

    GEMINI_API_KEYS = [
        k
        for k in (
            os.environ.get("GEMINI_API_KEY_1", ""),
            os.environ.get("GEMINI_API_KEY_2", ""),
            os.environ.get("GEMINI_API_KEY_3", ""),
            os.environ.get("GEMINI_API_KEY_4", ""),
        )
        if k
    ]
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    AI_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AI_REQUEST_TIMEOUT_SECONDS", 30))
    AI_KEY_COOLDOWN_SECONDS = int(os.environ.get("AI_KEY_COOLDOWN_SECONDS", 60))
    AI_CACHE_TTL_SECONDS = int(os.environ.get("AI_CACHE_TTL_SECONDS", 24 * 60 * 60))

    LOG_DIR = os.path.join(basedir, "logs")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MAIL_SERVER = ""  # force dev/console email backend in tests
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix="jobmarket_ai_test_uploads_")


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
