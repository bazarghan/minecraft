from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, MinecraftServer
from app.services.capacity import allocate_port


def server(*, deleted: bool) -> MinecraftServer:
    return MinecraftServer(
        name="reusable-server",
        slug="reusable-server",
        version="1.21.7",
        server_type="VANILLA",
        port=25565,
        memory_mb=2048,
        cpu_limit=2,
        rcon_password_encrypted="encrypted-test-password",
        deleted_at=datetime.now(UTC) if deleted else None,
    )


@pytest.mark.asyncio
async def test_soft_deleted_server_releases_name_slug_and_port() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as db:
        db.add(server(deleted=True))
        await db.commit()

        assert await allocate_port(db) == 25565

        db.add(server(deleted=False))
        await db.commit()

        conflicting = server(deleted=False)
        conflicting.name = "different-name"
        conflicting.slug = "different-slug"
        db.add(conflicting)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    await engine.dispose()
