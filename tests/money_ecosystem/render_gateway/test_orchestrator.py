from pathlib import Path

from money_ecosystem.render_gateway.asset_store import StoredArtifact
from money_ecosystem.render_gateway.contract import QualityTier, RenderJob
from money_ecosystem.render_gateway.orchestrator import RenderOrchestrator
from money_ecosystem.render_gateway.providers.base import (
    Estimate, ProviderCapabilities, ProviderJob, ProviderMode, ProviderPoll, ProviderStatus, StagedJob
)
from money_ecosystem.render_gateway.state import JobState


def _job():
    return RenderJob.from_dict({
        "job_id": "job-1", "attempt_id": "a1", "project_id": "max-bus",
        "job_type": "IMAGE_RENDER", "quality_tier": "FLOW_GRADE",
        "cost_policy": "USE_EXISTING_ENTITLEMENTS", "aspect_ratio": "16:9",
        "output_resolution": "1920x1080", "prompt": "Max beside bus",
        "negative_constraints": [], "assets": [],
        "scene_contract": {"required_entities": ["character.max"]},
        "max_attempts": 2, "return_mode": "CHAT_ATTACHMENT_PREFERRED",
    })


class FakeProvider:
    provider_id = "fake-flow"
    mode = ProviderMode.API
    def __init__(self, output: Path): self.output = output
    def preflight(self): return ProviderStatus(True, self.mode, authorization="AUTHENTICATED", entitlement="EXISTING", quota="AVAILABLE")
    def capabilities(self): return ProviderCapabilities(self.provider_id, QualityTier.FLOW_GRADE, ("IMAGE_RENDER",), ("multi_reference",))
    def estimate(self, job): return Estimate(1, 0.0, "USD", False, True)
    def stage_assets(self, job): return StagedJob(job, {})
    def submit(self, job): self.output.write_bytes(b"rendered"); return ProviderJob("p1", {})
    def poll(self, provider_job_id): return ProviderPoll(provider_job_id, "COMPLETE")
    def collect(self, provider_job_id): return [self.output]
    def cancel(self, provider_job_id): return None


class FakeStore:
    artifact_parent_id = "folder"
    def put(self, path, logical_role, parent_id, *, mime_type):
        return StoredArtifact("drive-out", logical_role, mime_type, path.stat().st_size, "a"*64, path.name, parent_id)


def test_orchestrator_reaches_complete(tmp_path: Path):
    provider = FakeProvider(tmp_path / "scene.png")
    orch = RenderOrchestrator(
        providers=[provider],
        asset_store=FakeStore(),
        qa_evaluator=lambda job, files: {"terminal_status": "VERIFIED"},
        workspace_root=tmp_path,
        chat_attachment_available=False,
    )
    result = orch.run(_job())
    assert result.state is JobState.COMPLETE
    assert result.state_history == (
        JobState.RECEIVED, JobState.ASSETS_STAGED, JobState.VALIDATED, JobState.ROUTED,
        JobState.QUEUED, JobState.RENDERING, JobState.QA, JobState.PACKAGING,
        JobState.RETURNING, JobState.COMPLETE,
    )
    assert result.return_manifest is not None


def test_flow_grade_without_qualifying_provider_fails_closed(tmp_path: Path):
    orch = RenderOrchestrator(
        providers=[], asset_store=FakeStore(), qa_evaluator=lambda *_: {}, workspace_root=tmp_path
    )
    result = orch.run(_job())
    assert result.state is JobState.QUALITY_TARGET_UNAVAILABLE
