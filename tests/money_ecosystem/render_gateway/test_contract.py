import pytest

from money_ecosystem.render_gateway.contract import CostPolicy, QualityTier, RenderJob


def _payload():
    return {
        "job_id": "job-1",
        "attempt_id": "a1",
        "project_id": "max-bus",
        "job_type": "IMAGE_RENDER",
        "quality_tier": "FLOW_GRADE",
        "cost_policy": "USE_EXISTING_ENTITLEMENTS",
        "aspect_ratio": "16:9",
        "output_resolution": "1920x1080",
        "prompt": "Max waves beside the bus",
        "negative_constraints": ["no extra characters"],
        "assets": [{
            "asset_id": "character.max",
            "drive_file_id": "drive-1",
            "logical_role": "character_reference",
            "mime_type": "image/png",
            "byte_size": 100,
            "sha256": "a" * 64,
            "source": "user_upload",
            "rights_note": "user supplied",
        }],
        "scene_contract": {"required_entities": ["character.max"]},
        "max_attempts": 3,
        "return_mode": "CHAT_ATTACHMENT_PREFERRED",
    }


def test_flow_grade_is_explicit_and_assets_are_hashed():
    job = RenderJob.from_dict(_payload())
    assert job.quality_tier is QualityTier.FLOW_GRADE
    assert job.cost_policy is CostPolicy.USE_EXISTING_ENTITLEMENTS
    assert job.assets[0].sha256 == "a" * 64


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("attempt_id", "", "attempt_id"),
        ("quality_tier", "UNKNOWN", "quality_tier"),
        ("cost_policy", "BUY_CREDITS", "cost_policy"),
        ("prompt", "   ", "prompt"),
        ("max_attempts", 0, "max_attempts"),
        ("max_attempts", 6, "max_attempts"),
    ],
)
def test_invalid_core_fields_are_rejected(field, value, message):
    payload = _payload()
    payload[field] = value
    with pytest.raises(ValueError, match=message):
        RenderJob.from_dict(payload)


def test_malformed_asset_sha_is_rejected():
    payload = _payload()
    payload["assets"][0]["sha256"] = "not-a-sha"
    with pytest.raises(ValueError, match="sha256"):
        RenderJob.from_dict(payload)


def test_scene_contract_is_required():
    payload = _payload()
    payload["scene_contract"] = {}
    with pytest.raises(ValueError, match="scene_contract"):
        RenderJob.from_dict(payload)
