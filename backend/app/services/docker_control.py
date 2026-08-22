import asyncio
from dataclasses import dataclass

import docker
from docker.errors import DockerException, NotFound

from ..config import get_settings
from ..models import MinecraftServer
from ..security import decrypt_secret


MANAGED_LABEL = "com.minecraft-manager.managed"
SERVER_ID_LABEL = "com.minecraft-manager.server-id"
PROJECT_LABEL = "com.minecraft-manager.project"
PROJECT_NAME = "minecraft-server-manager"


class ContainerSafetyError(RuntimeError):
    pass


@dataclass
class ContainerMetrics:
    status: str
    health: str | None
    cpu_percent: float
    memory_bytes: int
    exit_code: int | None


class DockerControl:
    """The only module allowed to talk to Docker; ownership is checked on every lookup."""

    def __init__(self):
        self.client = docker.from_env(timeout=30)
        self.settings = get_settings()

    @staticmethod
    def image_for(server: MinecraftServer) -> str:
        if server.version == "26.1.1":
            return "itzg/minecraft-server:java25"
        return "itzg/minecraft-server:java21"

    def _owned_container(self, server: MinecraftServer):
        if not server.container_id:
            raise NotFound("Server has no container")
        container = self.client.containers.get(server.container_id)
        labels = container.labels or {}
        if (
            labels.get(MANAGED_LABEL) != "true"
            or labels.get(SERVER_ID_LABEL) != str(server.id)
            or labels.get(PROJECT_LABEL) != PROJECT_NAME
        ):
            raise ContainerSafetyError("Refusing to manage a container without matching ownership labels")
        return container

    def create(self, server: MinecraftServer):
        data_root = self.settings.minecraft_data_root.resolve()
        data_dir = (data_root / str(server.id)).resolve()
        if data_root not in data_dir.parents:
            raise ContainerSafetyError("Resolved data path escaped the configured root")
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
        image = self.image_for(server)
        self.client.images.pull(image)
        heap_mb = max(768, int(server.memory_mb * 0.75))
        environment = {
            "EULA": "TRUE",
            "TYPE": server.server_type,
            "VERSION": server.version,
            "ONLINE_MODE": str(server.online_mode).upper(),
            "ENFORCE_SECURE_PROFILE": str(server.online_mode).upper(),
            "INIT_MEMORY": f"{max(512, min(heap_mb, server.memory_mb // 2))}M",
            "MAX_MEMORY": f"{heap_mb}M",
            "MAX_PLAYERS": str(server.max_players),
            "MODE": server.game_mode,
            "DIFFICULTY": server.difficulty,
            "PVP": str(server.pvp).upper(),
            "HARDCORE": str(server.hardcore).upper(),
            "MOTD": server.motd,
            "VIEW_DISTANCE": str(server.view_distance),
            "SIMULATION_DISTANCE": str(server.simulation_distance),
            "LEVEL": server.level_name,
            "ENABLE_RCON": "TRUE",
            "RCON_PASSWORD": decrypt_secret(server.rcon_password_encrypted),
            "UID": "10001",
            "GID": "10001",
        }
        if server.world_seed:
            environment["SEED"] = server.world_seed
        if server.whitelist:
            environment["WHITELIST"] = ",".join(server.whitelist)
            environment["ENFORCE_WHITELIST"] = "TRUE"
        if server.operators:
            environment["OPS"] = ",".join(server.operators)
        return self.client.containers.create(
            image=image,
            name=f"msm-{server.slug}",
            detach=True,
            environment=environment,
            labels={
                MANAGED_LABEL: "true",
                SERVER_ID_LABEL: str(server.id),
                PROJECT_LABEL: PROJECT_NAME,
            },
            ports={"25565/tcp": ("0.0.0.0", server.port)},
            volumes={str(data_dir): {"bind": "/data", "mode": "rw"}},
            mem_limit=f"{server.memory_mb}m",
            nano_cpus=int(server.cpu_limit * 1_000_000_000),
            restart_policy={"Name": server.restart_policy},
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            user="10001:10001",
        )

    def start(self, server: MinecraftServer) -> None:
        self._owned_container(server).start()

    def stop(self, server: MinecraftServer, timeout: int = 60) -> None:
        self._owned_container(server).stop(timeout=timeout)

    def kill(self, server: MinecraftServer) -> None:
        self._owned_container(server).kill()

    def restart(self, server: MinecraftServer, timeout: int = 60) -> None:
        self._owned_container(server).restart(timeout=timeout)

    def remove(self, server: MinecraftServer) -> None:
        try:
            self._owned_container(server).remove(force=False, v=False)
        except NotFound:
            return

    def logs(self, server: MinecraftServer, tail: int = 500) -> str:
        data = self._owned_container(server).logs(tail=min(max(tail, 1), 5000), timestamps=True)
        return data.decode("utf-8", errors="replace")

    def command(self, server: MinecraftServer, command: str) -> str:
        container = self._owned_container(server)
        result = container.exec_run(
            ["rcon-cli", "--password", decrypt_secret(server.rcon_password_encrypted), command],
            stdout=True,
            stderr=True,
        )
        if result.exit_code != 0:
            raise DockerException("RCON command failed")
        return result.output.decode("utf-8", errors="replace")[:65536]

    def metrics(self, server: MinecraftServer) -> ContainerMetrics:
        container = self._owned_container(server)
        container.reload()
        state = container.attrs.get("State", {})
        stats = container.stats(stream=False)
        cpu_delta = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) - stats.get(
            "precpu_stats", {}
        ).get("cpu_usage", {}).get("total_usage", 0)
        system_delta = stats.get("cpu_stats", {}).get("system_cpu_usage", 0) - stats.get(
            "precpu_stats", {}
        ).get("system_cpu_usage", 0)
        online_cpus = stats.get("cpu_stats", {}).get("online_cpus", 1) or 1
        cpu_percent = (cpu_delta / system_delta * online_cpus * 100) if system_delta > 0 else 0
        return ContainerMetrics(
            status=state.get("Status", container.status),
            health=state.get("Health", {}).get("Status"),
            cpu_percent=round(cpu_percent, 2),
            memory_bytes=stats.get("memory_stats", {}).get("usage", 0),
            exit_code=state.get("ExitCode"),
        )

    def reconcile(self) -> dict[str, dict]:
        containers = self.client.containers.list(
            all=True,
            filters={"label": [f"{MANAGED_LABEL}=true", f"{PROJECT_LABEL}={PROJECT_NAME}"]},
        )
        return {
            c.labels.get(SERVER_ID_LABEL): {
                "container_id": c.id,
                "status": c.status,
                "name": c.name,
            }
            for c in containers
            if c.labels.get(SERVER_ID_LABEL)
        }


async def run_docker(function, *args):
    return await asyncio.to_thread(function, *args)
