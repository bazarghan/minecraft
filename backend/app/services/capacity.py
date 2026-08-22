from dataclasses import asdict, dataclass

import psutil
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import MinecraftServer, Setting


CAPACITY_LOCK_ID = 0x4D534D


@dataclass
class Capacity:
    total_memory_mb: int
    reserved_host_memory_mb: int
    reserved_servers_memory_mb: int
    current_memory_used_mb: int
    allocatable_memory_mb: int
    cpu_percent: float
    cpu_count: int
    disk_total_bytes: int
    disk_used_bytes: int
    disk_percent: float
    overcommit_enabled: bool

    def to_dict(self) -> dict:
        return asdict(self)


async def lock_capacity(db: AsyncSession) -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": CAPACITY_LOCK_ID})


async def capacity_snapshot(db: AsyncSession) -> Capacity:
    settings = get_settings()
    reserved_setting = await db.get(Setting, "host_reserved_memory_mb")
    overcommit_setting = await db.get(Setting, "allow_memory_overcommit")
    host_reserved_mb = int(reserved_setting.value) if reserved_setting else settings.host_reserved_memory_mb
    overcommit = bool(overcommit_setting.value) if overcommit_setting else settings.allow_memory_overcommit
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    reserved = (
        await db.execute(
            select(func.coalesce(func.sum(MinecraftServer.memory_mb), 0)).where(
                MinecraftServer.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    total_mb = memory.total // (1024 * 1024)
    allocatable = max(0, total_mb - host_reserved_mb - int(reserved))
    return Capacity(
        total_memory_mb=total_mb,
        reserved_host_memory_mb=host_reserved_mb,
        reserved_servers_memory_mb=int(reserved),
        current_memory_used_mb=memory.used // (1024 * 1024),
        allocatable_memory_mb=allocatable,
        cpu_percent=psutil.cpu_percent(interval=None),
        cpu_count=psutil.cpu_count() or 1,
        disk_total_bytes=disk.total,
        disk_used_bytes=disk.used,
        disk_percent=disk.percent,
        overcommit_enabled=overcommit,
    )


async def require_capacity(db: AsyncSession, requested_mb: int, *, already_reserved_mb: int = 0) -> None:
    await lock_capacity(db)
    snapshot = await capacity_snapshot(db)
    effective_requested = max(0, requested_mb - already_reserved_mb)
    if not snapshot.overcommit_enabled and effective_requested > snapshot.allocatable_memory_mb:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Insufficient allocatable memory: requested {effective_requested} MB, "
                f"available {snapshot.allocatable_memory_mb} MB after host and server reservations"
            ),
        )


async def allocate_port(db: AsyncSession, requested: int | None = None) -> int:
    await lock_capacity(db)
    used = set(
        (await db.execute(select(MinecraftServer.port).where(MinecraftServer.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    if requested is not None:
        if requested in used:
            raise HTTPException(status_code=409, detail="Requested Minecraft port is already allocated")
        return requested
    for port in range(25565, 26001):
        if port not in used:
            return port
    raise HTTPException(status_code=409, detail="No free Minecraft ports are available")
