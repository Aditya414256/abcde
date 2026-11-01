import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file if present
load_dotenv(os.path.join(BASE_DIR, '.env'))


def normalize_database_url(url: str) -> str:
    """Ensures PostgreSQL URLs use the psycopg2 driver explicitly."""
    if not url:
        return url
    if url.startswith('postgres://'):
        return 'postgresql+psycopg2://' + url[len('postgres://'):]
    if url.startswith('postgresql://') and not url.startswith('postgresql+'):
        return 'postgresql+psycopg2://' + url[len('postgresql://'):]
    return url


class Config:
    """Base configuration. All sensitive values come from environment variables."""

    # SECRET_KEY: must be set in environment for production.
    # A hardcoded fallback is only used for local development convenience.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        _env = os.environ.get('FLASK_ENV', 'development')
        if _env == 'production':
            raise RuntimeError(
                "SECRET_KEY environment variable is not set. "
                "Set it to a long random string before running in production."
            )
        # Development fallback only
        SECRET_KEY = 'medifind-dev-only-secret-key-not-for-production'

    # Database: defaults to local SQLite for development.
    # For production, set DATABASE_URL to a PostgreSQL connection string.
    # Supabase PostgreSQL example:
    #   postgresql+psycopg2://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres?sslmode=require
    #   (use transaction pooler URL for Vercel serverless; direct URL for migrations)
    _raw_db_url = os.environ.get('DATABASE_URL')
    if _raw_db_url:
        SQLALCHEMY_DATABASE_URI = normalize_database_url(_raw_db_url)
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'medifind.db')}"

    # Supabase PostgreSQL: psycopg2 does not support prepared statements over
    # the transaction pooler. Disable them when using a pgbouncer/pooler URL.
    SQLALCHEMY_ENGINE_OPTIONS = {}
    if 'postgresql' in SQLALCHEMY_DATABASE_URI or 'postgres' in SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {'options': '-c statement_timeout=30000'},
        }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Supabase Storage Configuration ───────────────────────────────────────
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    SUPABASE_PRESCRIPTIONS_BUCKET = os.environ.get('SUPABASE_PRESCRIPTIONS_BUCKET', 'prescriptions')
    SUPABASE_PHARMACY_DOCS_BUCKET = os.environ.get('SUPABASE_PHARMACY_DOCS_BUCKET', 'pharmacy-docs')

    # Upload folder for local fallback storage (used when Supabase Storage is unset).
    UPLOAD_FOLDER = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(BASE_DIR, 'uploads', 'prescriptions'),
    )

    # Maximum upload size: 10 MB.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Set SESSION_COOKIE_SECURE = True in production (requires HTTPS)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'


class DevelopmentConfig(Config):
    """Local development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration. Requires all secrets via environment variables."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration. Uses in-memory SQLite."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # Override: no PG-specific connect_args for SQLite
    SECRET_KEY = 'test-secret-key-not-for-production'
    # Disable CSRF in tests
    WTF_CSRF_ENABLED = False
