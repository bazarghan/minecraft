import os


os.environ.setdefault("MSM_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("MSM_ENCRYPTION_KEY", "test-encryption-key-that-is-at-least-32-characters")
os.environ.setdefault("MSM_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MSM_REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("MSM_ENVIRONMENT", "test")
os.environ.setdefault("MSM_COOKIE_SECURE", "false")
