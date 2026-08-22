import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from ...audit import record_audit
from ...deps import CurrentUser, Db, Operator
from ...models import Backup, BackgroundJob, MinecraftServer, ServerStatus
from ...schemas import BackupCreate, BackupOut, JobOut
from ...tasks import backup_server, restore_server_backup


router = APIRouter(prefix="/backups", tags=["Backups"])


@router.get("", response_model=list[BackupOut])
async def list_backups(_: CurrentUser, db: Db, server_id: uuid.UUID | None = None, offset: int = 0, limit: int = 50):
    query = select(Backup).order_by(Backup.created_at.desc())
    if server_id:
        query = query.where(Backup.server_id == server_id)
    return (await db.execute(query.offset(max(offset, 0)).limit(min(limit, 100)))).scalars().all()


@router.post("/servers/{server_id}", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def create(server_id: uuid.UUID, payload: BackupCreate, request: Request, operator: Operator, db: Db):
    server = await db.get(MinecraftServer, server_id)
    if not server or server.deleted_at:
        raise HTTPException(status_code=404, detail="Server not found")
    job = BackgroundJob(job_type="backup_create", owner_id=operator.id)
    db.add(job)
    await db.flush()
    await record_audit(db, request, "backup.create", "queued", user=operator, target=str(server_id), details={"reason": payload.reason})
    await db.commit()
    backup_server.delay(str(job.id), str(server_id), payload.reason)
    await db.refresh(job)
    return job


@router.get("/{backup_id}/download")
async def download(backup_id: uuid.UUID, _: CurrentUser, db: Db):
    backup = await db.get(Backup, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    path = Path(backup.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Backup file is missing")
    return FileResponse(path, filename=f"minecraft-backup-{backup.created_at:%Y%m%d-%H%M%S}.tar.gz", media_type="application/gzip")


@router.post("/{backup_id}/restore", response_model=JobOut, status_code=202)
async def restore(backup_id: uuid.UUID, request: Request, operator: Operator, db: Db):
    backup = await db.get(Backup, backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    server = await db.get(MinecraftServer, backup.server_id)
    if not server or server.status not in {ServerStatus.stopped, ServerStatus.created}:
        raise HTTPException(status_code=409, detail="Stop the server before restoring a backup")
    job = BackgroundJob(job_type="backup_restore", owner_id=operator.id)
    db.add(job)
    await db.flush()
    await record_audit(db, request, "backup.restore", "queued", user=operator, target=str(backup_id), details={"server_id": str(server.id)})
    await db.commit()
    restore_server_backup.delay(str(job.id), str(backup_id))
    await db.refresh(job)
    return job
