import pytest
from pydantic import ValidationError

from app.schemas import ConsoleCommand, ServerCreate


def valid_server(**overrides):
    values = {
        "name": "Parkour One",
        "slug": "parkour-one",
        "version": "26.1.1",
        "server_type": "VANILLA",
        "eula_accepted": True,
    }
    values.update(overrides)
    return ServerCreate(**values)


def test_eula_must_be_explicitly_accepted() -> None:
    with pytest.raises(ValidationError):
        valid_server(eula_accepted=False)


def test_offline_mode_requires_separate_confirmation() -> None:
    with pytest.raises(ValidationError, match="offline mode requires"):
        valid_server(online_mode=False)
    assert valid_server(online_mode=False, offline_mode_confirmed=True).online_mode is False


def test_forge_26_is_not_allowlisted() -> None:
    with pytest.raises(ValidationError, match="Forge compatibility"):
        valid_server(server_type="FORGE")


def test_player_names_and_console_are_strictly_validated() -> None:
    with pytest.raises(ValidationError):
        valid_server(operators=["../../owner"])
    with pytest.raises(ValidationError):
        ConsoleCommand(command="say hello\nstop")
