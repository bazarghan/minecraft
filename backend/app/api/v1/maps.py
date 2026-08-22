import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select

from ...audit import record_audit
from ...config import get_settings
from ...deps import CurrentUser, Db, Operator
from ...models import BackgroundJob, JobStatus, Map
from ...schemas import JobOut, MapInstallRequest, MapOut, MapUrlImport
from ...tasks import import_map_url, install_map, register_map_archive


router = APIRouter(prefix="/maps", tags=["Map library"])


@router.get("", response_model=list[MapOut])
async def list_maps(_: CurrentUser, db: Db, offset: int = 0, limit: int = 50):
    return (
        await db.execute(select(Map).order_by(Map.created_at.desc()).offset(max(offset, 0)).limit(min(limit, 100)))
    ).scalars().all()


@router.post("/url", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def import_url(payload: MapUrlImport, request: Request, operator: Operator, db: Db):
    job = BackgroundJob(job_type="map_url_import", owner_id=operator.id)
    db.add(job)
    await db.flush()
    await record_audit(db, request, "map.import_url", "queued", user=operator, target=str(job.id), details={"host": payload.url.split("/", 3)[2] if "://" in payload.url else "invalid"})
    await db.commit()
    import_map_url.delay(str(job.id), payload.model_dump())
    await db.refresh(job)
    return job


@router.post("/upload", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_map(
    request: Request,
    operator: Operator,
    db: Db,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form(min_length=1, max_length=128)],
    description: Annotated[str, Form(max_length=2000)] = "",
    author: Annotated[str | None, Form(max_length=128)] = None,
    minecraft_version: Annotated[str | None, Form(max_length=32)] = None,
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=415, detail="Only .zip map uploads are accepted")
    settings = get_settings()
    staging = settings.map_library_root / "staging"
    staging.mkdir(parents=True, exist_ok=True, mode=0o750)
    target = staging / f"{uuid.uuid4()}.zip"
    maximum = settings.max_upload_mb * 1024 * 1024
    size = 0
    try:
        with target.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    job = BackgroundJob(job_type="map_upload", owner_id=operator.id)
    db.add(job)
    await db.flush()
    await record_audit(db, request, "map.upload", "queued", user=operator, target=str(job.id), details={"size": size})
    await db.commit()
    register_map_archive.delay(str(job.id), str(target), {"name": name, "description": description, "author": author, "minecraft_version": minecraft_version}, "upload", True)
    await db.refresh(job)
    return job


@router.post("/library", response_model=JobOut, status_code=202)
async def import_library_file(payload: dict, request: Request, operator: Operator, db: Db):
    settings = get_settings()
    incoming = (settings.map_library_root / "incoming").resolve()
    filename = str(payload.get("filename", ""))
    candidate = (incoming / filename).resolve()
    if incoming not in candidate.parents or not candidate.is_file() or candidate.is_symlink() or candidate.suffix.lower() != ".zip":
        raise HTTPException(status_code=400, detail="Select a valid ZIP from the server-side incoming map directory")
    name = str(payload.get("name", ""))[:128]
    if not name:
        raise HTTPException(status_code=422, detail="Map name is required")
    job = BackgroundJob(job_type="map_library_import", owner_id=operator.id)
    db.add(job)
    await db.flush()
    await record_audit(db, request, "map.import_library", "queued", user=operator, target=str(job.id), details={"filename": candidate.name})
    await db.commit()
    register_map_archive.delay(str(job.id), str(candidate), {"name": name, "description": str(payload.get("description", ""))[:2000], "author": str(payload.get("author", ""))[:128] or None, "minecraft_version": str(payload.get("minecraft_version", ""))[:32] or None}, "server-library", False)
    await db.refresh(job)
    return job


@router.post("/{map_id}/install", response_model=JobOut, status_code=202)
async def install(map_id: uuid.UUID, payload: MapInstallRequest, request: Request, operator: Operator, db: Db):
    if not await db.get(Map, map_id):
        raise HTTPException(status_code=404, detail="Map not found")
    job = BackgroundJob(job_type="map_install", owner_id=operator.id)
    db.add(job)
    await db.flush()
    await record_audit(db, request, "map.install", "queued", user=operator, target=str(map_id), details={"server_id": str(payload.server_id)})
    await db.commit()
    install_map.delay(str(job.id), str(map_id), str(payload.server_id), payload.restart_after_install)
    await db.refresh(job)
    return job
