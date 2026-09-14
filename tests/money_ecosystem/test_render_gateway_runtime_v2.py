from pathlib import Path

from money_ecosystem.worker.runtime_v2 import execute_job


def _gateway_job():
    return {
        "job_id": "gateway-1",
        "job_type": "RENDER_GATEWAY",
        "created_at": "2026-09-14T14:30:00Z",
        "args": {
            "render_job": {
                "job_id": "render-1",
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
                "max_attempts": 2,
                "return_mode": "CHAT_ATTACHMENT_PREFERRED",
            }
        },
    }


def test_gateway_runtime_fails_closed_without_flow_quality_provider(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CURIOUS_FLOW_AUTHENTICATED", raising=False)
    monkeypatch.delenv("CURIOUS_FLOW_CONNECTOR_AVAILABLE", raising=False)
    result = execute_job(_gateway_job(), tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["artifact_manifest"]["gateway_state"] in {"QUALITY_TARGET_UNAVAILABLE", "BLOCKED_AUTH"}
    assert result["artifact_manifest"]["quality_tier"] == "FLOW_GRADE"


def test_non_gateway_jobs_still_delegate_to_legacy_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "money_ecosystem.worker.runtime_v2.legacy_execute_job",
        lambda job, workspace_root: {"status": "SUCCESS", "message": "legacy", "artifact_manifest": {}},
    )
    result = execute_job({"job_id": "probe", "job_type": "MEDIA_PROBE", "created_at": "x", "args": {}}, tmp_path)
    assert result["status"] == "SUCCESS"
    assert result["message"] == "legacy"
