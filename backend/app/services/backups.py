import hashlib
import os
import shutil
import tarfile
import tempfile
import uuid
from pathlib import Path

from ..config import get_settings


class BackupSafetyError(RuntimeError):
    pass


def server_data_path(server_id: uuid.UUID) -> Path:
    root = get_settings().minecraft_data_root.resolve()
    path = (root / str(server_id)).resolve()
    if root not in path.parents:
        raise BackupSafetyError("Server data path escaped configured root")
    return path


def create_backup(server_id: uuid.UUID, backup_id: uuid.UUID) -> tuple[Path, int, str]:
    source = server_data_path(server_id)
    if not source.is_dir():
        raise BackupSafetyError("Server data directory does not exist")
    backup_dir = (get_settings().backup_root / str(server_id)).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
    destination = backup_dir / f"{backup_id}.tar.gz"
    with tarfile.open(destination, "x:gz") as archive:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise BackupSafetyError("Symbolic links are not permitted in server data")
            archive.add(path, arcname=path.relative_to(source), recursive=False)
    digest = hashlib.sha256()
    with destination.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return destination, destination.stat().st_size, digest.hexdigest()


def restore_backup(server_id: uuid.UUID, backup_path: Path) -> None:
    destination = server_data_path(server_id)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    staging = Path(tempfile.mkdtemp(prefix=f"msm-restore-{server_id}-", dir=destination.parent))
    old = destination.with_name(f"{destination.name}.restore-old")
    try:
        with tarfile.open(backup_path, "r:gz") as archive:
            members = archive.getmembers()
            if any(member.issym() or member.islnk() for member in members):
                raise BackupSafetyError("Backup contains links")
            for member in members:
                target = (staging / member.name).resolve()
                if staging.resolve() not in target.parents and target != staging.resolve():
                    raise BackupSafetyError("Backup contains an unsafe path")
            archive.extractall(staging, filter="data")
        if old.exists():
            raise BackupSafetyError("A previous restore recovery directory still exists")
        if destination.exists():
            os.replace(destination, old)
        os.replace(staging, destination)
        if old.exists():
            shutil.rmtree(old)
    except Exception:
        if not destination.exists() and old.exists():
            os.replace(old, destination)
        raise
