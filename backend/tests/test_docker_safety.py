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


@pytest.mark.parametrize(
    ("version", "tag"),
    [
        ("26.2", "java25"),
        ("26.1.1", "java25"),
        ("1.21.11", "java21"),
        ("1.20.6", "java21"),
        ("1.20.4", "java17"),
        ("1.18.2", "java17"),
        ("1.17.1", "java16"),
        ("1.16.5", "java8"),
        ("1.8.9", "java8"),
    ],
)
def test_selects_compatible_java_image(version: str, tag: str) -> None:
    item = server()
    item.version = version
    assert DockerControl.image_for(item) == f"itzg/minecraft-server:{tag}"
