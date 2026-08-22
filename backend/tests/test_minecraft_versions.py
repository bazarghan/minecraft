import pytest

from app.services.minecraft_versions import parse_version_manifest


def test_parses_all_official_version_types() -> None:
    payload = {
        "latest": {"release": "26.2", "snapshot": "26.3-snapshot-1"},
        "versions": [
            {"id": "26.3-snapshot-1", "type": "snapshot", "releaseTime": "2026-08-01"},
            {"id": "26.2", "type": "release", "releaseTime": "2026-06-16"},
            {"id": "20w14∞", "type": "snapshot", "releaseTime": "2020-04-01"},
            {"id": "b1.8.1", "type": "old_beta", "releaseTime": "2011-09-19"},
            {"id": "a1.2.6", "type": "old_alpha", "releaseTime": "2010-12-03"},
        ],
    }

    catalog = parse_version_manifest(payload)

    assert catalog["latest"] == "26.2"
    assert catalog["source"] == "mojang"
    assert [item["id"] for item in catalog["versions"]] == [
        "26.3-snapshot-1",
        "26.2",
        "20w14∞",
        "b1.8.1",
        "a1.2.6",
    ]


def test_rejects_an_invalid_manifest() -> None:
    with pytest.raises(ValueError, match="invalid structure"):
        parse_version_manifest({"versions": "not-a-list"})
