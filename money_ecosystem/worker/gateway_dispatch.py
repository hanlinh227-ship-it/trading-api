from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from money_ecosystem.render_gateway.contract import RenderJob
from money_ecosystem.render_gateway.state import JobState


def execute_render_gateway(
    outer_job: dict[str, Any],
    workspace_root: Path | str,
    orchestrator_factory: Callable[[Path | str], Any],
) -> dict[str, Any]:
    raw = outer_job.get("args", {}).get("render_job")
    if not isinstance(raw, dict):
        return {
            "status": "BLOCKED",
            "message": "RENDER_GATEWAY requires args.render_job",
            "artifact_manifest": {"render_gateway": {"state": "BLOCKED_ASSET"}},
        }

    outer_job_id = str(outer_job.get("job_id", "")).strip()
    inner_job_id = str(raw.get("job_id", "")).strip()
    if outer_job_id != inner_job_id:
        return {
            "status": "BLOCKED",
            "message": f"RENDER_GATEWAY job_id mismatch: outer={outer_job_id!r}, inner={inner_job_id!r}",
            "artifact_manifest": {"render_gateway": {"state": "BLOCKED_ASSET"}},
        }

    try:
        render_job = RenderJob.from_dict(raw)
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "message": f"RENDER_GATEWAY contract rejected: {exc}",
            "artifact_manifest": {"render_gateway": {"state": "BLOCKED_ASSET"}},
        }

    try:
        orchestrator = orchestrator_factory(workspace_root)
        result = orchestrator.run(render_job)
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "message": f"RENDER_GATEWAY orchestration failed: {exc}",
            "artifact_manifest": {"render_gateway": {"state": "RENDER_FAILED"}},
        }

    result_payload = result.to_dict()
    state_value = result.state.value if isinstance(result.state, JobState) else str(result.state)
    return {
        "status": "SUCCESS" if state_value == JobState.COMPLETE.value else "BLOCKED",
        "message": str(result.message),
        "artifact_manifest": {
            "render_gateway": result_payload,
            "quality_tier": render_job.quality_tier.value,
            "cost_policy": render_job.cost_policy.value,
            "auto_purchase": False,
            "silent_quality_downgrade": False,
        },
    }
