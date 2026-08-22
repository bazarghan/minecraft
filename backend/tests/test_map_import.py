import os
import stat
import zipfile
from pathlib import Path

import pytest

from app.services.map_import import (
    UnsafeMapError,
    _validate_public_url,
    extract_world,
    inspect_zip,
    store_archive,
)


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


def test_allows_small_highly_compressible_minecraft_region_files(tmp_path: Path) -> None:
    archive = tmp_path / "world.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as source:
        source.writestr("world/level.dat", b"level")
        source.writestr("world/region/r.0.0.mca", b"\0" * 8192)

    assert inspect_zip(archive) == (2, 8197)


def test_rejects_large_highly_compressible_entries(tmp_path: Path) -> None:
    archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as source:
        source.writestr("world/level.dat", b"level")
        source.writestr("world/region/r.0.0.mca", b"\0" * (2 * 1024 * 1024))

    with pytest.raises(UnsafeMapError, match="suspicious compression ratio"):
        inspect_zip(archive)


def test_stores_download_via_destination_filesystem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "download"
    library = tmp_path / "library"
    source_dir.mkdir()
    library.mkdir()
    source = source_dir / "map.zip"
    destination = library / "checksum.zip"
    source.write_bytes(b"map data")
    real_replace = os.replace
    replacements: list[tuple[Path, Path]] = []

    def record_replace(staged: str | Path, target: str | Path) -> None:
        replacements.append((Path(staged), Path(target)))
        real_replace(staged, target)

    monkeypatch.setattr("app.services.map_import.os.replace", record_replace)
    store_archive(source, destination)

    assert destination.read_bytes() == b"map data"
    assert not source.exists()
    assert replacements[0][0].parent == library
    assert replacements[0][1] == destination


def test_storing_duplicate_archive_keeps_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "download.zip"
    destination = tmp_path / "existing.zip"
    source.write_bytes(b"duplicate")
    destination.write_bytes(b"existing")

    store_archive(source, destination)

    assert destination.read_bytes() == b"existing"
    assert not source.exists()


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/map.zip", "http://169.254.169.254/latest", "http://[::1]/map.zip"])
def test_url_validation_blocks_unsupported_and_private_targets(url: str) -> None:
    with pytest.raises(UnsafeMapError):
        _validate_public_url(url)
