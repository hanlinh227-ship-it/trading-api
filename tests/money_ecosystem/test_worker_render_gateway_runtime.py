from __future__ import annotations

from dataclasses import dataclass

from money_ecosystem.render_gateway.state import JobState
from money_ecosystem.worker import runtime


def _render_job(job_id: str = "gateway-test") -> dict:
    return {
        "job_id": job_id,
        "attempt_id": "a1",
        "project_id": "max-bus",
        "job_type": "IMAGE_RENDER",
        "quality_tier": "FLOW_GRADE",
        "cost_policy": "USE_EXISTING_ENTITLEMENTS",
        "aspect_ratio": "16:9",
        "output_resolution": "1920x1080",
        "prompt": "Max waves beside the bus",
        "negative_constraints": ["no extra characters"],
        "assets": [],
        "scene_contract": {"required_entities": ["character.max", "vehicle.bus"]},
        "max_attempts": 2,
        "return_mode": "CHAT_ATTACHMENT_PREFERRED",
    }


def _gateway_job(inner_job_id: str = "gateway-test") -> dict:
    return {
        "job_id": "gateway-test",
        "job_type": "RENDER_GATEWAY",
        "created_at": "2026-09-14T21:20:00+07:00",
        "args": {"render_job": _render_job(inner_job_id)},
    }


@dataclass(frozen=True)
class FakeResult:
    state: JobState = JobState.COMPLETE
    message: str = "done"

    def to_dict(self):
        return {
            "state": self.state.value,
            "message": self.message,
            "state_history": [JobState.RECEIVED.value, JobState.COMPLETE.value],
            "return_manifest": {"return_mode": "DRIVE_CARD", "artifacts": []},
        }


class FakeOrchestrator:
    def __init__(self):
        self.seen = []

    def run(self, job):
        self.seen.append(job)
        return FakeResult()


def test_render_gateway_dispatches_to_v2_orchestrator(monkeypatch, tmp_path):
    fake = FakeOrchestrator()
    monkeypatch.setattr(runtime, "_build_render_gateway_orchestrator", lambda workspace: fake, raising=False)

    result = runtime.execute_job(_gateway_job(), tmp_path)

    assert result["status"] == "SUCCESS"
    assert result["artifact_manifest"]["render_gateway"]["state"] == "COMPLETE"
    assert fake.seen and fake.seen[0].quality_tier.value == "FLOW_GRADE"


def test_render_gateway_rejects_outer_inner_job_id_mismatch(tmp_path):
    result = runtime.execute_job(_gateway_job("different-inner-id"), tmp_path)
    assert result["status"] == "BLOCKED"
    assert "job_id" in result["message"]
