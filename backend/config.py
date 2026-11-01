import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    """Base configuration. All sensitive values must come from environment variables."""

    # SECRET_KEY: must be set in environment for production.
    # A hardcoded fallback is only used for local development convenience.
    # In production, set SECRET_KEY to a long random string and never commit it.
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
    #   postgresql+psycopg2://postgres:<password>@<host>:5432/postgres
    #   (use transaction pooler URL for Vercel serverless; direct URL for migrations)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'medifind.db')}"
    )

    # Supabase PostgreSQL: psycopg2 does not support prepared statements over
    # the transaction pooler. Disable them when using a pgbouncer/pooler URL.
    _db_url = os.environ.get('DATABASE_URL', '')
    SQLALCHEMY_ENGINE_OPTIONS = {}
    if 'postgresql' in _db_url or 'postgres' in _db_url:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {'options': '-c statement_timeout=30000'},
        }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload folder for prescriptions (protected, not served directly without auth check).
    # On Vercel (serverless) the local filesystem is ephemeral; use Supabase Storage
    # for persistent prescription files in production.
    UPLOAD_FOLDER = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(BASE_DIR, 'uploads', 'prescriptions'),
    )

    # Maximum upload size: 10 MB. Vercel has a 4.5 MB body limit on its serverless
    # functions, so in production use direct-to-Supabase signed uploads instead of
    # routing files through this server.
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

    # Enforce HTTPS cookies in production
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration. Uses in-memory SQLite."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key-not-for-production'
    # Disable CSRF in tests
    WTF_CSRF_ENABLED = False
