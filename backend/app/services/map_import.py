import hashlib
import ipaddress
import shutil
import socket
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx

from ..config import get_settings


class UnsafeMapError(ValueError):
    pass


MAX_COMPRESSION_RATIO = 200
MIN_RATIO_CHECK_BYTES = 1024 * 1024


def _safe_destination(root: Path, member_name: str) -> Path:
    pure = PurePosixPath(member_name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or "\x00" in member_name:
        raise UnsafeMapError("Archive contains an unsafe path")
    if any(part in {"", "."} for part in pure.parts):
        raise UnsafeMapError("Archive contains an invalid filename")
    destination = (root / Path(*pure.parts)).resolve()
    if root.resolve() not in destination.parents and destination != root.resolve():
        raise UnsafeMapError("Archive path escaped staging directory")
    return destination


def inspect_zip(archive: Path) -> tuple[int, int]:
    settings = get_settings()
    total_size = 0
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if len(members) > settings.max_archive_files:
            raise UnsafeMapError("Archive contains too many files")
        for member in members:
            _safe_destination(Path("/staging"), member.filename)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise UnsafeMapError("Archive contains a symbolic link")
            total_size += member.file_size
            if total_size > settings.max_extracted_mb * 1024 * 1024:
                raise UnsafeMapError("Archive expands beyond the configured limit")
            # Empty Minecraft region files can legitimately compress from 8 KiB
            # to only a few bytes. A high ratio is only dangerous when the entry
            # is also large enough to consume meaningful extraction resources.
            if (
                member.file_size >= MIN_RATIO_CHECK_BYTES
                and member.file_size > member.compress_size * MAX_COMPRESSION_RATIO
            ):
                raise UnsafeMapError("Archive contains a suspicious compression ratio")
    return len(members), total_size


def extract_world(archive: Path, destination: Path) -> Path:
    inspect_zip(archive)
    destination.mkdir(parents=True, exist_ok=False, mode=0o750)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = _safe_destination(destination, member.filename)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(member) as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
    candidates = [destination] + [p for p in destination.iterdir() if p.is_dir()]
    worlds = [path for path in candidates if (path / "level.dat").is_file()]
    if len(worlds) != 1:
        raise UnsafeMapError("Archive must contain exactly one plausible world with level.dat")
    return worlds[0]


def _validate_public_url(url: str) -> set[str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise UnsafeMapError("Only unauthenticated HTTP and HTTPS URLs are permitted")
    if parsed.port and parsed.port not in {80, 443}:
        raise UnsafeMapError("Only standard HTTP and HTTPS ports are permitted")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeMapError("Download hostname could not be resolved") from exc
    validated: set[str] = set()
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeMapError("Private, loopback, link-local, and reserved addresses are blocked")
        validated.add(ip.compressed)
    return validated


def download_map(url: str, destination: Path) -> tuple[str, int]:
    settings = get_settings()
    current = url
    digest = hashlib.sha256()
    size = 0
    timeout = httpx.Timeout(settings.download_timeout_seconds, connect=10)
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for redirect_count in range(settings.max_redirects + 1):
            validated_addresses = _validate_public_url(current)
            with client.stream("GET", current, headers={"User-Agent": "MinecraftServerManager/0.1"}) as response:
                stream = response.extensions.get("network_stream")
                peer = stream.get_extra_info("server_addr") if stream else None
                peer_ip = ipaddress.ip_address(peer[0]).compressed if peer else None
                if peer_ip not in validated_addresses:
                    raise UnsafeMapError("Download peer did not match the validated DNS answers")
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirect_count >= settings.max_redirects:
                        raise UnsafeMapError("Download exceeded the redirect limit")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                declared = int(response.headers.get("content-length", "0") or 0)
                maximum = settings.max_upload_mb * 1024 * 1024
                if declared > maximum:
                    raise UnsafeMapError("Download exceeds the configured size limit")
                with destination.open("xb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > maximum:
                            raise UnsafeMapError("Download exceeds the configured size limit")
                        digest.update(chunk)
                        output.write(chunk)
                return digest.hexdigest(), size
    raise UnsafeMapError("Download could not be completed")


def stage_download(url: str) -> tuple[Path, str, int]:
    staging = Path(tempfile.mkdtemp(prefix="msm-map-"))
    archive = staging / "map.zip"
    try:
        checksum, size = download_map(url, archive)
        inspect_zip(archive)
        return archive, checksum, size
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
