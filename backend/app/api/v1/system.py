import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ...audit import record_audit
from ...config import get_settings
from ...database import SessionLocal
from ...deps import Admin, CurrentUser, Db
from ...models import AuditEvent, BackgroundJob, MinecraftServer, ServerStatus, Setting
from ...schemas import AuditOut, JobOut, SettingUpdate
from ...services.capacity import capacity_snapshot


router = APIRouter(tags=["Host and application"])


@router.get("/host/capacity")
async def host_capacity(_: CurrentUser, db: Db):
    return (await capacity_snapshot(db)).to_dict()


@router.get("/host/metrics")
async def host_metrics(_: CurrentUser, db: Db):
    capacity = (await capacity_snapshot(db)).to_dict()
    status_counts = dict(
        (await db.execute(select(MinecraftServer.status, func.count()).where(MinecraftServer.deleted_at.is_(None)).group_by(MinecraftServer.status))).all()
    )
    capacity["servers"] = {state.value: status_counts.get(state, 0) for state in ServerStatus}
    return capacity


@router.get("/events")
async def event_stream(_: CurrentUser):
    async def events():
        last_id: uuid.UUID | None = None
        while True:
            async with SessionLocal() as db:
                query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(25)
                rows = list((await db.execute(query)).scalars().all())
                new_rows = rows if last_id is None else [row for row in rows if row.id != last_id]
                if rows:
                    last_id = rows[0].id
                payload = [AuditOut.model_validate(row).model_dump(mode="json") for row in reversed(new_rows)]
                yield f"event: update\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/audit", response_model=list[AuditOut])
async def audit_log(_: Admin, db: Db, offset: int = 0, limit: int = 50):
    return (
        await db.execute(select(AuditEvent).order_by(AuditEvent.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 100)))
    ).scalars().all()


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(_: CurrentUser, db: Db, offset: int = 0, limit: int = 50):
    return (
        await db.execute(select(BackgroundJob).order_by(BackgroundJob.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 100)))
    ).scalars().all()


@router.get("/jobs/{job_id}", response_model=JobOut)
async def job_detail(job_id: uuid.UUID, _: CurrentUser, db: Db):
    job = await db.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/settings")
async def application_settings(_: Admin, db: Db):
    configured = {item.key: item.value for item in (await db.execute(select(Setting))).scalars()}
    defaults = get_settings()
    return {
        "host_reserved_memory_mb": configured.get("host_reserved_memory_mb", defaults.host_reserved_memory_mb),
        "allow_memory_overcommit": configured.get("allow_memory_overcommit", defaults.allow_memory_overcommit),
        "backup_retention_count": configured.get("backup_retention_count", 10),
        "scheduled_backup_interval_hours": configured.get("scheduled_backup_interval_hours", 24),
    }


@router.patch("/settings")
async def update_settings(payload: SettingUpdate, request: Request, admin: Admin, db: Db):
    for key, value in payload.model_dump(exclude_unset=True).items():
        entry = await db.get(Setting, key)
        if entry:
            entry.value = value
            entry.updated_at = datetime.now(UTC)
        else:
            db.add(Setting(key=key, value=value))
    await record_audit(db, request, "settings.update", "success", user=admin, details=payload.model_dump(exclude_unset=True))
    await db.commit()
    return await application_settings(admin, db)
