from pathlib import Path

from money_ecosystem.render_gateway.artifacts import package_and_upload, select_return_mode
from money_ecosystem.render_gateway.asset_store import StoredArtifact
from money_ecosystem.render_gateway.contract import RenderJob, ReturnMode


def _job(return_mode="CHAT_ATTACHMENT_PREFERRED"):
    return RenderJob.from_dict({
        "job_id": "job-1",
        "attempt_id": "a1",
        "project_id": "max-bus",
        "job_type": "IMAGE_RENDER",
        "quality_tier": "FLOW_GRADE",
        "cost_policy": "USE_EXISTING_ENTITLEMENTS",
        "aspect_ratio": "16:9",
        "output_resolution": "1920x1080",
        "prompt": "Max beside bus",
        "negative_constraints": [],
        "assets": [],
        "scene_contract": {"required_entities": ["character.max"]},
        "max_attempts": 3,
        "return_mode": return_mode,
    })


class FakeStore:
    artifact_parent_id = "drive-folder"

    def put(self, path: Path, logical_role: str, parent_id: str, *, mime_type: str):
        return StoredArtifact(
            drive_file_id=f"drive-{path.name}",
            logical_role=logical_role,
            mime_type=mime_type,
            byte_size=path.stat().st_size,
            sha256="a" * 64,
            source_name=path.name,
            parent_id=parent_id,
        )


def test_return_mode_falls_back_in_declared_order():
    assert select_return_mode(ReturnMode.CHAT_ATTACHMENT_PREFERRED, chat_attachment_available=True) is ReturnMode.CHAT_ATTACHMENT_PREFERRED
    assert select_return_mode(ReturnMode.CHAT_ATTACHMENT_PREFERRED, chat_attachment_available=False) is ReturnMode.DRIVE_CARD
    assert select_return_mode(ReturnMode.DRIVE_CARD, chat_attachment_available=False) is ReturnMode.DRIVE_CARD


def test_package_upload_records_hash_metadata(tmp_path: Path):
    image = tmp_path / "scene_01.png"
    image.write_bytes(b"png-bytes")
    manifest = package_and_upload(
        _job(),
        [image],
        {"terminal_status": "VERIFIED"},
        FakeStore(),
        chat_attachment_available=False,
    )
    assert manifest.return_mode is ReturnMode.DRIVE_CARD
    assert len(manifest.artifacts) == 1
    artifact = manifest.artifacts[0]
    assert artifact.drive_file_id == "drive-scene_01.png"
    assert artifact.sha256 == "a" * 64
    assert artifact.byte_size == len(b"png-bytes")
    assert artifact.qa_summary["terminal_status"] == "VERIFIED"
