import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class ServerStatus(str, enum.Enum):
    created = "created"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    stopped = "stopped"
    failed = "failed"
    deleting = "deleting"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Session(TimestampMixin, Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    user: Mapped[User] = relationship(back_populates="sessions")


class MinecraftServer(TimestampMixin, Base):
    __tablename__ = "minecraft_servers"
    __table_args__ = (
        Index(
            "uq_minecraft_servers_active_name",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_minecraft_servers_active_slug",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_minecraft_servers_active_port",
            "port",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    server_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[ServerStatus] = mapped_column(Enum(ServerStatus), default=ServerStatus.created)
    container_id: Mapped[str | None] = mapped_column(String(128))
    port: Mapped[int] = mapped_column(Integer)
    memory_mb: Mapped[int] = mapped_column(Integer)
    cpu_limit: Mapped[float] = mapped_column()
    max_players: Mapped[int] = mapped_column(Integer, default=20)
    game_mode: Mapped[str] = mapped_column(String(16), default="survival")
    difficulty: Mapped[str] = mapped_column(String(16), default="normal")
    pvp: Mapped[bool] = mapped_column(Boolean, default=True)
    hardcore: Mapped[bool] = mapped_column(Boolean, default=False)
    view_distance: Mapped[int] = mapped_column(Integer, default=10)
    simulation_distance: Mapped[int] = mapped_column(Integer, default=10)
    motd: Mapped[str] = mapped_column(String(256), default="A Minecraft Server")
    world_seed: Mapped[str | None] = mapped_column(String(128))
    level_name: Mapped[str] = mapped_column(String(64), default="world")
    online_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    whitelist: Mapped[list[str]] = mapped_column(JSON, default=list)
    operators: Mapped[list[str]] = mapped_column(JSON, default=list)
    restart_policy: Mapped[str] = mapped_column(String(32), default="unless-stopped")
    rcon_password_encrypted: Mapped[str] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Map(TimestampMixin, Base):
    __tablename__ = "maps"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(64))
    minecraft_version: Mapped[str | None] = mapped_column(String(32))
    file_size: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    source: Mapped[str] = mapped_column(String(2048))
    storage_path: Mapped[str] = mapped_column(String(2048))
    preview_path: Mapped[str | None] = mapped_column(String(2048))
    compatibility_status: Mapped[str] = mapped_column(String(32), default="unknown")


class Backup(TimestampMixin, Base):
    __tablename__ = "backups"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("minecraft_servers.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(128))
    storage_path: Mapped[str] = mapped_column(String(2048))
    file_size: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64))


class BackgroundJob(TimestampMixin, Base):
    __tablename__ = "background_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128), index=True)
    target: Mapped[str | None] = mapped_column(String(256))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PortAllocation(Base):
    __tablename__ = "port_allocations"
    __table_args__ = (UniqueConstraint("port", name="uq_port_allocations_port"),)
    port: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("minecraft_servers.id", ondelete="CASCADE"), unique=True
    )
