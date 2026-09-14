from pathlib import Path

import pytest

from money_ecosystem.render_gateway.asset_store import AssetIntegrityError
from money_ecosystem.render_gateway.contract import AssetRef
from money_ecosystem.render_gateway.drive_store import DriveAssetStore


def _asset(sha256: str) -> AssetRef:
    return AssetRef(
        asset_id="character.max",
        drive_file_id="drive-1",
        logical_role="character_reference",
        mime_type="image/png",
        byte_size=4,
        sha256=sha256,
        source="user_upload",
        rights_note="user supplied",
    )


def test_fetch_rejects_checksum_mismatch(tmp_path: Path):
    store = DriveAssetStore(
        downloader=lambda file_id: b"data",
        uploader=lambda path, role, parent_id, mime: {"id": "unused"},
    )
    with pytest.raises(AssetIntegrityError, match="SHA256"):
        store.fetch(_asset("0" * 64), tmp_path / "ref.png")


def test_fetch_accepts_matching_checksum(tmp_path: Path):
    store = DriveAssetStore(
        downloader=lambda file_id: b"data",
        uploader=lambda path, role, parent_id, mime: {"id": "unused"},
    )
    asset = _asset("3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7")
    target = store.fetch(asset, tmp_path / "ref.png")
    assert target.read_bytes() == b"data"


def test_put_hashes_uploaded_file(tmp_path: Path):
    source = tmp_path / "scene.png"
    source.write_bytes(b"final")
    store = DriveAssetStore(
        downloader=lambda file_id: b"",
        uploader=lambda path, role, parent_id, mime: {
            "id": "drive-out",
            "mimeType": mime,
            "size": str(path.stat().st_size),
        },
    )
    result = store.put(source, "final_image", "folder-1", mime_type="image/png")
    assert result.drive_file_id == "drive-out"
    assert result.sha256 == "2443630b4620165c8a102e4287b6e2d800aa4b1530c37d9c19d963e24ea3b44a"
    assert result.byte_size == 5
