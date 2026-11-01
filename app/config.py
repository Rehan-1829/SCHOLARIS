import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _database_uri() -> str:
    """Use DATABASE_URL when provided, otherwise a local SQLite file.

    Hosts hand out ``postgres://`` and plain ``postgresql://`` URLs. Both are
    rewritten to the psycopg 3 dialect that requirements.txt installs, and
    ``postgres://`` also has to be renamed because SQLAlchemy 2.x rejects it.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return f"sqlite:///{BASE_DIR / 'instance' / 'scholaris.db'}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-before-deploying")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Shown in the header and used to scope invoices/enrolments.
    CURRENT_TERM = os.environ.get("CURRENT_TERM", "2026-27 · Odd semester")
    COLLEGE_NAME = "Scholaris College of Applied Sciences"

    # Attendance below this percentage is flagged as a shortage.
    ATTENDANCE_THRESHOLD = 75

    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Login throttling: attempts allowed per email within the window.
    LOGIN_MAX_ATTEMPTS = 6
    LOGIN_WINDOW_MINUTES = 10


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False
    CURRENT_TERM = "2026-27 · Odd semester"
