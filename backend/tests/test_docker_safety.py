import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models import MinecraftServer
from app.services.docker_control import (
    MANAGED_LABEL,
    PROJECT_LABEL,
    PROJECT_NAME,
    SERVER_ID_LABEL,
    ContainerSafetyError,
    DockerControl,
)


def server() -> MinecraftServer:
    item = MinecraftServer(
        id=uuid.uuid4(), name="Safe", slug="safe", version="26.1.1", server_type="VANILLA",
        port=25565, memory_mb=2048, cpu_limit=2, rcon_password_encrypted="unused", container_id="container-id",
    )
    return item


def control_with(container):
    control = object.__new__(DockerControl)
    control.client = SimpleNamespace(containers=SimpleNamespace(get=MagicMock(return_value=container)))
    return control


def test_refuses_unrelated_container() -> None:
    item = server()
    with pytest.raises(ContainerSafetyError):
        control_with(SimpleNamespace(labels={}))._owned_container(item)


def test_accepts_only_all_matching_ownership_labels() -> None:
    item = server()
    container = SimpleNamespace(labels={MANAGED_LABEL: "true", SERVER_ID_LABEL: str(item.id), PROJECT_LABEL: PROJECT_NAME})
    assert control_with(container)._owned_container(item) is container
