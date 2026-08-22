import stat
import zipfile
from pathlib import Path

import pytest

from app.services.map_import import UnsafeMapError, _validate_public_url, extract_world, inspect_zip


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def test_extracts_single_plausible_world(tmp_path: Path) -> None:
    archive = tmp_path / "world.zip"
    make_zip(archive, {"My World/level.dat": b"level", "My World/region/r.0.0.mca": b"region"})
    world = extract_world(archive, tmp_path / "out")
    assert world.name == "My World"
    assert (world / "level.dat").read_bytes() == b"level"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "safe/../../escape", "..\\escape"])
def test_rejects_zip_path_traversal(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "bad.zip"
    make_zip(archive, {name: b"bad", "level.dat": b"level"})
    with pytest.raises(UnsafeMapError, match="unsafe path"):
        inspect_zip(archive)


def test_rejects_zip_symlink(tmp_path: Path) -> None:
    archive = tmp_path / "link.zip"
    with zipfile.ZipFile(archive, "w") as source:
        info = zipfile.ZipInfo("world/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        source.writestr(info, "target")
        source.writestr("world/level.dat", b"level")
    with pytest.raises(UnsafeMapError, match="symbolic link"):
        inspect_zip(archive)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/map.zip", "http://169.254.169.254/latest", "http://[::1]/map.zip"])
def test_url_validation_blocks_unsupported_and_private_targets(url: str) -> None:
    with pytest.raises(UnsafeMapError):
        _validate_public_url(url)
