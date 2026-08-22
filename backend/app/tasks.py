import hashlib
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DbSession

from .config import get_settings
from .models import Backup, BackgroundJob, JobStatus, Map, MinecraftServer, ServerStatus, Setting
from .services.backups import create_backup, restore_backup, server_data_path
from .services.docker_control import DockerControl
from .services.map_import import extract_world, inspect_zip, stage_download


settings = get_settings()
celery = Celery("minecraft-manager", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "reconcile-every-minute": {"task": "reconcile", "schedule": 60.0},
        "scheduled-backup-scan": {"task": "scheduled_backups", "schedule": 3600.0},
    },
)
sync_engine = create_engine(settings.database_url.replace("+psycopg", ""), pool_pre_ping=True)


def _job(db: DbSession, job_id: str) -> BackgroundJob:
    job = db.get(BackgroundJob, uuid.UUID(job_id))
    if not job:
        raise RuntimeError("Background job does not exist")
    return job


def _fail_job(job_id: str, exc: Exception) -> None:
    with DbSession(sync_engine) as db:
        job = _job(db, job_id)
        job.status = JobStatus.failed
        job.error = f"{type(exc).__name__}: operation failed; inspect worker logs"
        db.commit()


@celery.task(name="import_map_url", autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def import_map_url(job_id: str, metadata: dict) -> None:
    archive = None
    try:
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            job.status = JobStatus.running
            job.progress = 10
            db.commit()
        archive, checksum, size = stage_download(metadata["url"])
        destination = (settings.map_library_root / f"{checksum}.zip").resolve()
        settings.map_library_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        if settings.map_library_root.resolve() not in destination.parents:
            raise RuntimeError("Map storage path is unsafe")
        if destination.exists():
            archive.unlink()
        else:
            os.replace(archive, destination)
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            existing = db.scalar(select(Map).where(Map.checksum_sha256 == checksum))
            map_entry = existing or Map(
                name=metadata["name"],
                description=metadata.get("description", ""),
                author=metadata.get("author"),
                minecraft_version=metadata.get("minecraft_version"),
                file_size=size,
                checksum_sha256=checksum,
                source=metadata["url"],
                storage_path=str(destination),
                compatibility_status="compatible" if metadata.get("minecraft_version") else "unknown",
            )
            if not existing:
                db.add(map_entry)
                db.flush()
            job.status = JobStatus.succeeded
            job.progress = 100
            job.result = {"map_id": str(map_entry.id)}
            db.commit()
    except Exception as exc:
        _fail_job(job_id, exc)
        raise
    finally:
        if archive:
            shutil.rmtree(archive.parent, ignore_errors=True)


@celery.task(name="register_map_archive")
def register_map_archive(job_id: str, archive_path: str, metadata: dict, source: str, remove_source: bool) -> None:
    try:
        source_path = Path(archive_path).resolve()
        library = settings.map_library_root.resolve()
        if library not in source_path.parents:
            raise RuntimeError("Map archive is outside the configured library")
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            job.status = JobStatus.running
            job.progress = 20
            db.commit()
        inspect_zip(source_path)
        digest = hashlib.sha256()
        with source_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        checksum = digest.hexdigest()
        destination = library / f"{checksum}.zip"
        if not destination.exists():
            if remove_source:
                os.replace(source_path, destination)
            else:
                shutil.copy2(source_path, destination)
        elif remove_source:
            source_path.unlink(missing_ok=True)
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            existing = db.scalar(select(Map).where(Map.checksum_sha256 == checksum))
            entry = existing or Map(
                name=metadata["name"],
                description=metadata.get("description", ""),
                author=metadata.get("author"),
                minecraft_version=metadata.get("minecraft_version"),
                file_size=destination.stat().st_size,
                checksum_sha256=checksum,
                source=source,
                storage_path=str(destination),
                compatibility_status="compatible" if metadata.get("minecraft_version") else "unknown",
            )
            if not existing:
                db.add(entry)
                db.flush()
            job.status = JobStatus.succeeded
            job.progress = 100
            job.result = {"map_id": str(entry.id)}
            db.commit()
    except Exception as exc:
        _fail_job(job_id, exc)
        raise


@celery.task(name="create_backup", autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def backup_server(job_id: str, server_id: str, reason: str) -> None:
    try:
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            job.status = JobStatus.running
            job.progress = 10
            server = db.get(MinecraftServer, uuid.UUID(server_id))
            if not server:
                raise RuntimeError("Server does not exist")
            if server.status == ServerStatus.running:
                DockerControl().command(server, "save-all flush")
                DockerControl().command(server, "save-off")
            backup_id = uuid.uuid4()
            path, size, checksum = create_backup(server.id, backup_id)
            if server.status == ServerStatus.running:
                DockerControl().command(server, "save-on")
            backup = Backup(
                id=backup_id,
                server_id=server.id,
                reason=reason,
                storage_path=str(path),
                file_size=size,
                checksum_sha256=checksum,
            )
            db.add(backup)
            db.flush()
            retention_setting = db.get(Setting, "backup_retention_count")
            retention = int(retention_setting.value) if retention_setting else 10
            expired = list(
                db.scalars(
                    select(Backup)
                    .where(Backup.server_id == server.id)
                    .order_by(Backup.created_at.desc())
                    .offset(retention)
                )
            )
            backup_root = settings.backup_root.resolve()
            for old_backup in expired:
                old_path = Path(old_backup.storage_path).resolve()
                if backup_root in old_path.parents:
                    old_path.unlink(missing_ok=True)
                db.delete(old_backup)
            job.status = JobStatus.succeeded
            job.progress = 100
            job.result = {"backup_id": str(backup.id)}
            db.commit()
    except Exception as exc:
        _fail_job(job_id, exc)
        raise


@celery.task(name="restore_backup")
def restore_server_backup(job_id: str, backup_id: str) -> None:
    try:
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            job.status = JobStatus.running
            backup = db.get(Backup, uuid.UUID(backup_id))
            if not backup:
                raise RuntimeError("Backup does not exist")
            server = db.get(MinecraftServer, backup.server_id)
            if not server or server.status not in {ServerStatus.stopped, ServerStatus.created}:
                raise RuntimeError("Server must be stopped before restore")
            safety_id = uuid.uuid4()
            safety_path, size, checksum = create_backup(server.id, safety_id)
            db.add(Backup(id=safety_id, server_id=server.id, reason="automatic-pre-restore", storage_path=str(safety_path), file_size=size, checksum_sha256=checksum))
            restore_backup(server.id, Path(backup.storage_path))
            job.status = JobStatus.succeeded
            job.progress = 100
            job.result = {"backup_id": backup_id, "safety_backup_id": str(safety_id)}
            db.commit()
    except Exception as exc:
        _fail_job(job_id, exc)
        raise


@celery.task(name="install_map")
def install_map(job_id: str, map_id: str, server_id: str, restart_after: bool) -> None:
    staging = None
    try:
        with DbSession(sync_engine) as db:
            job = _job(db, job_id)
            job.status = JobStatus.running
            map_entry = db.get(Map, uuid.UUID(map_id))
            server = db.get(MinecraftServer, uuid.UUID(server_id))
            if not map_entry or not server:
                raise RuntimeError("Map or server does not exist")
            control = DockerControl()
            was_running = server.status == ServerStatus.running
            if was_running:
                control.stop(server)
                server.status = ServerStatus.stopped
            backup_id = uuid.uuid4()
            path, size, checksum = create_backup(server.id, backup_id)
            db.add(Backup(id=backup_id, server_id=server.id, reason="automatic-pre-map-install", storage_path=str(path), file_size=size, checksum_sha256=checksum))
            staging = Path(tempfile.mkdtemp(prefix="msm-map-install-", dir=server_data_path(server.id).parent))
            world = extract_world(Path(map_entry.storage_path), staging / "extracted")
            destination = server_data_path(server.id) / server.level_name
            old = destination.with_name(f"{destination.name}.map-old")
            if old.exists():
                raise RuntimeError("Map recovery directory already exists")
            if destination.exists():
                os.replace(destination, old)
            try:
                shutil.copytree(world, destination)
            except Exception:
                shutil.rmtree(destination, ignore_errors=True)
                if old.exists():
                    os.replace(old, destination)
                raise
            if old.exists():
                shutil.rmtree(old)
            if (restart_after or was_running) and server.container_id:
                control.start(server)
                server.status = ServerStatus.running
                server.last_started_at = datetime.now(UTC)
            job.status = JobStatus.succeeded
            job.progress = 100
            job.result = {"server_id": server_id, "backup_id": str(backup_id)}
            db.commit()
    except Exception as exc:
        _fail_job(job_id, exc)
        raise
    finally:
        if staging:
            shutil.rmtree(staging, ignore_errors=True)


@celery.task(name="reconcile")
def reconcile() -> None:
    actual = DockerControl().reconcile()
    mapping = {"running": ServerStatus.running, "created": ServerStatus.created, "exited": ServerStatus.stopped, "dead": ServerStatus.failed}
    with DbSession(sync_engine) as db:
        for server in db.scalars(select(MinecraftServer).where(MinecraftServer.deleted_at.is_(None))):
            state = actual.get(str(server.id))
            if state:
                server.container_id = state["container_id"]
                server.status = mapping.get(state["status"], server.status)
            elif server.container_id:
                server.status = ServerStatus.failed
                server.last_error = "Managed container is missing during reconciliation"
        db.commit()


@celery.task(name="scheduled_backups")
def scheduled_backups() -> None:
    with DbSession(sync_engine) as db:
        interval_setting = db.get(Setting, "scheduled_backup_interval_hours")
        interval = int(interval_setting.value) if interval_setting else 24
        cutoff = datetime.now(UTC) - timedelta(hours=interval)
        for server in db.scalars(select(MinecraftServer).where(MinecraftServer.deleted_at.is_(None))):
            latest = db.scalar(
                select(Backup.created_at)
                .where(Backup.server_id == server.id, Backup.reason == "scheduled")
                .order_by(Backup.created_at.desc())
                .limit(1)
            )
            if latest is None or latest < cutoff:
                job = BackgroundJob(job_type="backup_create")
                db.add(job)
                db.flush()
                backup_server.delay(str(job.id), str(server.id), "scheduled")
        db.commit()
