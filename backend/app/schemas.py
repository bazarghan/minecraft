import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from .models import JobStatus, Role, ServerStatus


Username = Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")]
Slug = Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict | None = None


class LoginRequest(BaseModel):
    username: Username
    password: SecretStr = Field(min_length=12, max_length=256)


class UserCreate(BaseModel):
    username: Username
    password: SecretStr = Field(min_length=12, max_length=256)
    role: Role


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr = Field(min_length=12, max_length=256)


class UserOut(ORMModel):
    id: uuid.UUID
    username: str
    role: Role
    is_active: bool
    created_at: datetime


class SessionOut(ORMModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    revoked_at: datetime | None


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str


class ServerCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100)]
    slug: Slug
    version: Annotated[str, Field(min_length=1, max_length=32)] = "26.2"
    server_type: Literal["VANILLA", "PAPER", "FABRIC", "FORGE"] = "VANILLA"
    eula_accepted: Literal[True]
    memory_mb: int = Field(default=2048, ge=1024, le=131072, multiple_of=256)
    cpu_limit: float = Field(default=2.0, gt=0, le=128)
    max_players: int = Field(default=20, ge=1, le=1000)
    game_mode: Literal["survival", "creative", "adventure", "spectator"] = "survival"
    difficulty: Literal["peaceful", "easy", "normal", "hard"] = "normal"
    pvp: bool = True
    hardcore: bool = False
    view_distance: int = Field(default=10, ge=2, le=32)
    simulation_distance: int = Field(default=10, ge=2, le=32)
    motd: str = Field(default="A Minecraft Server", max_length=256)
    world_seed: str | None = Field(default=None, max_length=128)
    level_name: str = Field(default="world", min_length=1, max_length=64)
    online_mode: bool = True
    offline_mode_confirmed: bool = False
    whitelist: list[str] = Field(default_factory=list, max_length=1000)
    operators: list[str] = Field(default_factory=list, max_length=100)
    restart_policy: Literal["no", "on-failure", "unless-stopped"] = "unless-stopped"
    port: int | None = Field(default=None, ge=1024, le=65535)

    @field_validator("name", "level_name")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value) or "/" in value or "\\" in value:
            raise ValueError("contains unsafe characters")
        return value.strip()

    @field_validator("whitelist", "operators")
    @classmethod
    def validate_players(cls, values: list[str]) -> list[str]:
        pattern = re.compile(r"^[A-Za-z0-9_]{3,16}$")
        if any(not pattern.fullmatch(value) for value in values):
            raise ValueError("contains an invalid Minecraft username")
        return sorted(set(values))

    @model_validator(mode="after")
    def confirm_offline_mode(self) -> "ServerCreate":
        if not self.online_mode and not self.offline_mode_confirmed:
            raise ValueError("offline mode requires explicit security confirmation")
        return self


class ServerUpdate(BaseModel):
    max_players: int | None = Field(default=None, ge=1, le=1000)
    game_mode: Literal["survival", "creative", "adventure", "spectator"] | None = None
    difficulty: Literal["peaceful", "easy", "normal", "hard"] | None = None
    pvp: bool | None = None
    hardcore: bool | None = None
    view_distance: int | None = Field(default=None, ge=2, le=32)
    simulation_distance: int | None = Field(default=None, ge=2, le=32)
    motd: str | None = Field(default=None, max_length=256)
    whitelist: list[str] | None = None
    operators: list[str] | None = None
    restart_policy: Literal["no", "on-failure", "unless-stopped"] | None = None


class ServerRecreate(BaseModel):
    version: str | None = Field(default=None, min_length=1, max_length=32)
    server_type: Literal["VANILLA", "PAPER", "FABRIC", "FORGE"] | None = None
    memory_mb: int | None = Field(default=None, ge=1024, le=131072, multiple_of=256)
    cpu_limit: float | None = Field(default=None, gt=0, le=128)


class ServerOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    version: str
    server_type: str
    status: ServerStatus
    port: int
    memory_mb: int
    cpu_limit: float
    max_players: int
    game_mode: str
    difficulty: str
    pvp: bool
    hardcore: bool
    view_distance: int
    simulation_distance: int
    motd: str
    level_name: str
    online_mode: bool
    whitelist: list[str]
    operators: list[str]
    restart_policy: str
    last_error: str | None
    last_started_at: datetime | None
    created_at: datetime


class LifecycleRequest(BaseModel):
    confirmation: str | None = Field(default=None, max_length=100)


class ConsoleCommand(BaseModel):
    command: str = Field(min_length=1, max_length=512)

    @field_validator("command")
    @classmethod
    def single_line(cls, value: str) -> str:
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("must be a single command")
        return value


class MapUrlImport(BaseModel):
    url: str = Field(max_length=2048)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    author: str | None = Field(default=None, max_length=128)
    minecraft_version: str | None = Field(default=None, max_length=32)


class MapInstallRequest(BaseModel):
    server_id: uuid.UUID
    restart_after_install: bool = True


class MapOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    author: str | None
    version: str | None
    minecraft_version: str | None
    file_size: int
    checksum_sha256: str
    source: str
    compatibility_status: str
    created_at: datetime


class BackupCreate(BaseModel):
    reason: str = Field(default="manual", max_length=128)


class BackupOut(ORMModel):
    id: uuid.UUID
    server_id: uuid.UUID
    reason: str
    file_size: int
    checksum_sha256: str
    created_at: datetime


class JobOut(ORMModel):
    id: uuid.UUID
    job_type: str
    status: JobStatus
    progress: int
    result: dict | None
    error: str | None
    created_at: datetime


class AuditOut(ORMModel):
    id: uuid.UUID
    username: str | None
    action: str
    target: str | None
    ip_address: str | None
    result: str
    details: dict
    request_id: str | None
    created_at: datetime


class SettingUpdate(BaseModel):
    host_reserved_memory_mb: int | None = Field(default=None, ge=512)
    allow_memory_overcommit: bool | None = None
    backup_retention_count: int | None = Field(default=None, ge=1, le=1000)
    scheduled_backup_interval_hours: int | None = Field(default=None, ge=1, le=720)
