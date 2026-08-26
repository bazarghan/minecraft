import asyncio
import shutil
import uuid
from datetime import UTC, datetime

from docker.errors import DockerException, NotFound
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...audit import record_audit
from ...deps import CurrentUser, Db, Operator
from ...models import Backup, MinecraftServer, ServerStatus
from ...schemas import ConsoleCommand, LifecycleRequest, ServerCreate, ServerOut, ServerRecreate, ServerUpdate
from ...security import encrypt_secret, random_token
from ...services.capacity import allocate_port, require_capacity
from ...services.docker_control import ContainerSafetyError, DockerControl, run_docker
from ...services.backups import create_backup, server_data_path


router = APIRouter(prefix="/servers", tags=["Minecraft servers"])
TRANSITIONAL = {ServerStatus.starting, ServerStatus.stopping, ServerStatus.deleting}


def _creation_conflict_message(exc: IntegrityError) -> str:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint in {"minecraft_servers_port_key", "uq_minecraft_servers_active_port"}:
        return "Minecraft port is already allocated"
    if constraint in {
        "minecraft_servers_name_key",
        "ix_minecraft_servers_slug",
        "uq_minecraft_servers_active_name",
        "uq_minecraft_servers_active_slug",
    }:
        return "Server name or slug already exists"
    return "Server name, slug, or port conflicts with another active server"


async def get_server(db: Db, server_id: uuid.UUID, *, locked: bool = False) -> MinecraftServer:
    query = select(MinecraftServer).where(
        MinecraftServer.id == server_id, MinecraftServer.deleted_at.is_(None)
    )
    if locked:
        query = query.with_for_update()
    server = (await db.execute(query)).scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.get("", response_model=list[ServerOut])
async def list_servers(_: CurrentUser, db: Db, offset: int = 0, limit: int = 50):
    return (
        await db.execute(
            select(MinecraftServer)
            .where(MinecraftServer.deleted_at.is_(None))
            .order_by(MinecraftServer.name)
            .offset(max(offset, 0))
            .limit(min(limit, 100))
        )
    ).scalars().all()


@router.post("", response_model=ServerOut, status_code=status.HTTP_201_CREATED)
async def create_server(payload: ServerCreate, request: Request, operator: Operator, db: Db):
    if (
        await db.execute(
            select(MinecraftServer.id).where(
                (MinecraftServer.name == payload.name) | (MinecraftServer.slug == payload.slug),
                MinecraftServer.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Server name or slug already exists")
    await require_capacity(db, payload.memory_mb)
    port = await allocate_port(db, payload.port)
    values = payload.model_dump(exclude={"eula_accepted", "offline_mode_confirmed", "port"})
    server = MinecraftServer(
        **values,
        port=port,
        rcon_password_encrypted=encrypt_secret(random_token(32)),
    )
    db.add(server)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=_creation_conflict_message(exc)) from exc
    try:
        container = await run_docker(DockerControl().create, server)
        server.container_id = container.id
        server.status = ServerStatus.created
        await record_audit(db, request, "server.create", "success", user=operator, target=str(server.id))
    except Exception as exc:
        server.status = ServerStatus.failed
        server.last_error = "Container creation failed; inspect host logs with the request ID"
        await record_audit(db, request, "server.create", "failed", user=operator, target=str(server.id), details={"error_type": type(exc).__name__})
    await db.commit()
    await db.refresh(server)
    return server


@router.get("/{server_id}", response_model=ServerOut)
async def server_detail(server_id: uuid.UUID, _: CurrentUser, db: Db):
    return await get_server(db, server_id)


@router.patch("/{server_id}", response_model=ServerOut)
async def update_server(server_id: uuid.UUID, payload: ServerUpdate, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id, locked=True)
    if server.status in TRANSITIONAL:
        raise HTTPException(status_code=409, detail="A conflicting server operation is in progress")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(server, key, value)
    await record_audit(db, request, "server.update", "success", user=operator, target=str(server.id), details=payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(server)
    return server


async def _operate(server_id: uuid.UUID, action: str, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id, locked=True)
    allowed = {
        "start": {ServerStatus.created, ServerStatus.stopped, ServerStatus.failed},
        "stop": {ServerStatus.running, ServerStatus.starting},
        "restart": {ServerStatus.running},
    }
    if server.status not in allowed[action]:
        raise HTTPException(status_code=409, detail=f"Cannot {action} a server in {server.status.value} state")
    if action == "start":
        await require_capacity(db, server.memory_mb, already_reserved_mb=server.memory_mb)
        server.status = ServerStatus.starting
    elif action == "stop":
        server.status = ServerStatus.stopping
    await db.flush()
    try:
        control = DockerControl()
        if action == "start":
            if not server.container_id:
                container = await run_docker(control.create, server)
                server.container_id = container.id
            await run_docker(control.start, server)
            server.status = ServerStatus.running
            server.last_started_at = datetime.now(UTC)
        elif action == "stop":
            await run_docker(control.stop, server)
            server.status = ServerStatus.stopped
        else:
            await run_docker(control.restart, server)
            server.last_started_at = datetime.now(UTC)
        server.last_error = None
        await record_audit(db, request, f"server.{action}", "success", user=operator, target=str(server.id))
    except (DockerException, ContainerSafetyError) as exc:
        server.status = ServerStatus.failed
        server.last_error = f"{action.capitalize()} failed; inspect host logs with request ID"
        await record_audit(db, request, f"server.{action}", "failed", user=operator, target=str(server.id), details={"error_type": type(exc).__name__})
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Container {action} failed") from exc
    await db.commit()
    await db.refresh(server)
    return server


@router.post("/{server_id}/recreate", response_model=ServerOut)
async def recreate_server(server_id: uuid.UUID, payload: ServerRecreate, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id, locked=True)
    if server.status not in {ServerStatus.created, ServerStatus.stopped, ServerStatus.failed}:
        raise HTTPException(status_code=409, detail="Stop the server before recreating it")
    new_memory = payload.memory_mb or server.memory_mb
    await require_capacity(db, new_memory, already_reserved_mb=server.memory_mb)
    backup_id = uuid.uuid4()
    try:
        path, size, checksum = await asyncio.to_thread(create_backup, server.id, backup_id)
        db.add(Backup(id=backup_id, server_id=server.id, reason="automatic-pre-upgrade", storage_path=str(path), file_size=size, checksum_sha256=checksum))
        control = DockerControl()
        if server.container_id:
            await run_docker(control.remove, server)
            server.container_id = None
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(server, key, value)
        container = await run_docker(control.create, server)
        server.container_id = container.id
        server.status = ServerStatus.created
        server.last_error = None
        await record_audit(db, request, "server.recreate", "success", user=operator, target=str(server.id), details={"backup_id": str(backup_id)})
        await db.commit()
        await db.refresh(server)
        return server
    except HTTPException:
        raise
    except Exception as exc:
        server.status = ServerStatus.failed
        server.last_error = "Recreate failed; persistent data and pre-upgrade backup were preserved"
        await record_audit(db, request, "server.recreate", "failed", user=operator, target=str(server.id), details={"error_type": type(exc).__name__})
        await db.commit()
        raise HTTPException(status_code=502, detail="Container recreate failed; data was preserved") from exc


@router.post("/{server_id}/icon", status_code=204)
async def upload_icon(server_id: uuid.UUID, request: Request, operator: Operator, db: Db, file: UploadFile = File(...)):
    server = await get_server(db, server_id)
    body = await file.read(1024 * 1024 + 1)
    await file.close()
    if len(body) > 1024 * 1024 or not body.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="Server icon must be a PNG no larger than 1 MB")
    data_path = server_data_path(server.id)
    data_path.mkdir(parents=True, exist_ok=True, mode=0o750)
    target = data_path / "server-icon.png"
    await asyncio.to_thread(target.write_bytes, body)
    await record_audit(db, request, "server.icon_update", "success", user=operator, target=str(server.id))
    await db.commit()


@router.post("/{server_id}/start", response_model=ServerOut)
async def start(server_id: uuid.UUID, request: Request, operator: Operator, db: Db):
    return await _operate(server_id, "start", request, operator, db)


@router.post("/{server_id}/stop", response_model=ServerOut)
async def stop(server_id: uuid.UUID, request: Request, operator: Operator, db: Db):
    return await _operate(server_id, "stop", request, operator, db)


@router.post("/{server_id}/restart", response_model=ServerOut)
async def restart(server_id: uuid.UUID, request: Request, operator: Operator, db: Db):
    return await _operate(server_id, "restart", request, operator, db)


@router.post("/{server_id}/force-stop", response_model=ServerOut)
async def force_stop(server_id: uuid.UUID, payload: LifecycleRequest, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id, locked=True)
    if payload.confirmation != server.name:
        raise HTTPException(status_code=400, detail="Type the exact server name to confirm force stop")
    try:
        await run_docker(DockerControl().kill, server)
        server.status = ServerStatus.stopped
        await record_audit(db, request, "server.force_stop", "success", user=operator, target=str(server.id))
        await db.commit()
        await db.refresh(server)
        return server
    except (DockerException, ContainerSafetyError) as exc:
        raise HTTPException(status_code=502, detail="Force stop failed") from exc


@router.post("/{server_id}/duplicate", response_model=ServerOut, status_code=201)
async def duplicate_server(server_id: uuid.UUID, payload: dict, request: Request, operator: Operator, db: Db):
    source = await get_server(db, server_id)
    new_name = str(payload.get("name", ""))[:100]
    new_slug = str(payload.get("slug", ""))[:64]
    create = ServerCreate(
        name=new_name,
        slug=new_slug,
        version=source.version,
        server_type=source.server_type,
        eula_accepted=True,
        memory_mb=source.memory_mb,
        cpu_limit=source.cpu_limit,
        max_players=source.max_players,
        game_mode=source.game_mode,
        difficulty=source.difficulty,
        pvp=source.pvp,
        hardcore=source.hardcore,
        view_distance=source.view_distance,
        simulation_distance=source.simulation_distance,
        motd=source.motd,
        level_name=source.level_name,
        online_mode=source.online_mode,
        offline_mode_confirmed=not source.online_mode,
        whitelist=source.whitelist,
        operators=source.operators,
        restart_policy=source.restart_policy,
    )
    return await create_server(create, request, operator, db)


@router.get("/{server_id}/logs")
async def logs(server_id: uuid.UUID, _: CurrentUser, db: Db, tail: int = Query(default=500, ge=1, le=5000)):
    server = await get_server(db, server_id)
    try:
        return {"logs": await run_docker(DockerControl().logs, server, tail)}
    except (DockerException, ContainerSafetyError) as exc:
        raise HTTPException(status_code=502, detail="Logs are unavailable") from exc


@router.get("/{server_id}/logs/download")
async def download_logs(server_id: uuid.UUID, _: CurrentUser, db: Db):
    server = await get_server(db, server_id)
    try:
        body = await run_docker(DockerControl().logs, server, 5000)
    except (DockerException, ContainerSafetyError) as exc:
        raise HTTPException(status_code=502, detail="Logs are unavailable") from exc
    return Response(body, media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="{server.slug}.log"'})


@router.post("/{server_id}/console")
async def console(server_id: uuid.UUID, payload: ConsoleCommand, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id)
    if server.status != ServerStatus.running:
        raise HTTPException(status_code=409, detail="Console commands require a running server")
    try:
        output = await run_docker(DockerControl().command, server, payload.command)
        await record_audit(db, request, "server.console", "success", user=operator, target=str(server.id), details={"command": payload.command.split(" ", 1)[0]})
        await db.commit()
        return {"output": output}
    except (DockerException, ContainerSafetyError) as exc:
        raise HTTPException(status_code=502, detail="Console command failed") from exc


@router.get("/{server_id}/metrics")
async def metrics(server_id: uuid.UUID, _: CurrentUser, db: Db):
    server = await get_server(db, server_id)
    try:
        metrics = await run_docker(DockerControl().metrics, server)
        return metrics.__dict__
    except (DockerException, ContainerSafetyError, NotFound):
        return {"status": server.status.value, "health": None, "cpu_percent": 0, "memory_bytes": 0, "exit_code": None}


@router.delete("/{server_id}", status_code=204)
async def delete_preserve_data(server_id: uuid.UUID, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id, locked=True)
    if server.status in {ServerStatus.running, *TRANSITIONAL}:
        raise HTTPException(status_code=409, detail="Stop the server before deleting its container")
    server.status = ServerStatus.deleting
    await db.flush()
    try:
        await run_docker(DockerControl().remove, server)
    except (DockerException, ContainerSafetyError) as exc:
        raise HTTPException(status_code=502, detail="Container deletion failed") from exc
    server.container_id = None
    server.status = ServerStatus.stopped
    await record_audit(db, request, "server.delete_container", "success", user=operator, target=str(server.id), details={"data_preserved": True})
    await db.commit()


@router.delete("/{server_id}/data", status_code=204)
async def permanently_delete(server_id: uuid.UUID, payload: LifecycleRequest, request: Request, operator: Operator, db: Db):
    server = await get_server(db, server_id, locked=True)
    if payload.confirmation != server.name:
        raise HTTPException(status_code=400, detail="Type the exact server name to permanently delete it")
    if server.status in {ServerStatus.running, *TRANSITIONAL}:
        raise HTTPException(status_code=409, detail="Stop and remove the container before permanent deletion")
    if server.container_id:
        raise HTTPException(status_code=409, detail="Delete the container first; its data is still recoverable")
    data_root = DockerControl().settings.minecraft_data_root.resolve()
    data_path = (data_root / str(server.id)).resolve()
    if data_root not in data_path.parents:
        raise HTTPException(status_code=500, detail="Configured data path is unsafe")
    if data_path.exists():
        backup_id = uuid.uuid4()
        path, size, checksum = await asyncio.to_thread(create_backup, server.id, backup_id)
        db.add(Backup(id=backup_id, server_id=server.id, reason="automatic-pre-permanent-delete", storage_path=str(path), file_size=size, checksum_sha256=checksum))
        await asyncio.to_thread(shutil.rmtree, data_path)
    server.deleted_at = datetime.now(UTC)
    await record_audit(db, request, "server.delete_data", "success", user=operator, target=str(server.id), details={"recoverable": False})
    await db.commit()
