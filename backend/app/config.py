from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="MSM_", case_sensitive=False, extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "production"
    database_url: str = "postgresql+psycopg://manager@postgres/manager"
    redis_url: str = "redis://redis:6379/0"
    secret_key: SecretStr
    encryption_key: SecretStr
    public_url: str = "https://minecraft.example.com"
    cookie_name: str = "msm_session"
    cookie_secure: bool = True
    session_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    lockout_minutes: int = Field(default=15, ge=1, le=1440)
    host_reserved_memory_mb: int = Field(default=2048, ge=512)
    allow_memory_overcommit: bool = False
    minecraft_data_root: Path = Path("/srv/minecraft-manager/servers")
    map_library_root: Path = Path("/srv/minecraft-manager/maps")
    backup_root: Path = Path("/srv/minecraft-manager/backups")
    max_upload_mb: int = Field(default=1024, ge=1, le=10240)
    max_extracted_mb: int = Field(default=4096, ge=1, le=51200)
    max_archive_files: int = Field(default=20000, ge=10, le=100000)
    download_timeout_seconds: int = Field(default=60, ge=5, le=600)
    max_redirects: int = Field(default=3, ge=0, le=10)
    docs_enabled: bool = False
    initial_admin_username: str | None = None
    initial_admin_password: SecretStr | None = None

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("must contain at least 32 characters")
        return value

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
