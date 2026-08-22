import threading
import time
from typing import Any

import httpx


MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
CACHE_TTL_SECONDS = 6 * 60 * 60
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
VERSION_TYPES = {"release", "snapshot", "old_beta", "old_alpha"}

_FALLBACK_VERSIONS = [
    {"id": "26.2", "type": "release", "release_time": "2026-06-16T00:00:00Z"},
    {"id": "26.1.1", "type": "release", "release_time": "2026-03-01T00:00:00Z"},
    {"id": "1.21.11", "type": "release", "release_time": "2025-12-09T00:00:00Z"},
    {"id": "1.21.4", "type": "release", "release_time": "2024-12-03T00:00:00Z"},
    {"id": "1.20.6", "type": "release", "release_time": "2024-04-29T00:00:00Z"},
    {"id": "1.20.4", "type": "release", "release_time": "2023-12-07T00:00:00Z"},
    {"id": "1.19.4", "type": "release", "release_time": "2023-03-14T00:00:00Z"},
    {"id": "1.18.2", "type": "release", "release_time": "2022-02-28T00:00:00Z"},
    {"id": "1.17.1", "type": "release", "release_time": "2021-07-06T00:00:00Z"},
    {"id": "1.16.5", "type": "release", "release_time": "2021-01-15T00:00:00Z"},
    {"id": "1.12.2", "type": "release", "release_time": "2017-09-18T00:00:00Z"},
    {"id": "1.8.9", "type": "release", "release_time": "2015-12-09T00:00:00Z"},
]

_cache_lock = threading.Lock()
_cached_catalog: dict[str, Any] | None = None
_cache_expires_at = 0.0


def parse_version_manifest(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("versions"), list):
        raise ValueError("Mojang version manifest has an invalid structure")

    versions: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in payload["versions"]:
        if not isinstance(item, dict):
            continue
        version_id = item.get("id")
        version_type = item.get("type")
        release_time = item.get("releaseTime")
        if (
            not isinstance(version_id, str)
            or not 1 <= len(version_id) <= 32
            or any(ord(char) < 32 or ord(char) == 127 for char in version_id)
            or version_id in seen
            or version_type not in VERSION_TYPES
            or not isinstance(release_time, str)
        ):
            continue
        versions.append(
            {"id": version_id, "type": version_type, "release_time": release_time}
        )
        seen.add(version_id)

    latest_block = payload.get("latest")
    latest = latest_block.get("release") if isinstance(latest_block, dict) else None
    if not isinstance(latest, str) or latest not in seen:
        latest = next(
            (item["id"] for item in versions if item["type"] == "release"), "26.2"
        )
    if not versions:
        raise ValueError("Mojang version manifest contained no usable versions")
    return {"latest": latest, "source": "mojang", "versions": versions}


def _fallback_catalog() -> dict[str, Any]:
    return {"latest": "26.2", "source": "fallback", "versions": _FALLBACK_VERSIONS}


def get_version_catalog() -> dict[str, Any]:
    global _cached_catalog, _cache_expires_at

    now = time.monotonic()
    if _cached_catalog is not None and now < _cache_expires_at:
        return _cached_catalog

    with _cache_lock:
        now = time.monotonic()
        if _cached_catalog is not None and now < _cache_expires_at:
            return _cached_catalog
        try:
            with httpx.Client(
                timeout=httpx.Timeout(8, connect=5), follow_redirects=False, trust_env=False
            ) as client:
                response = client.get(MANIFEST_URL, headers={"Accept": "application/json"})
                response.raise_for_status()
                if len(response.content) > MAX_MANIFEST_BYTES:
                    raise ValueError("Mojang version manifest exceeded the size limit")
                catalog = parse_version_manifest(response.json())
        except (httpx.HTTPError, ValueError):
            catalog = _cached_catalog or _fallback_catalog()

        _cached_catalog = catalog
        _cache_expires_at = now + CACHE_TTL_SECONDS
        return catalog
