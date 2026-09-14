from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from money_ecosystem.render_gateway.contract import QualityTier, RenderJob
from money_ecosystem.render_gateway.drive_store import DriveAssetStore
from money_ecosystem.render_gateway.orchestrator import RenderOrchestrator
from money_ecosystem.render_gateway.providers.google_flow_image import GoogleFlowImageProvider
from money_ecosystem.render_gateway.providers.google_flow_video import GoogleFlowVideoProvider
from money_ecosystem.render_gateway.providers.local_comfyui import LocalComfyUIProvider
from money_ecosystem.render_gateway.providers.runway import RunwayProvider

from .allowlist import validate_job_request
from .runtime import execute_job as legacy_execute_job

RUNTIME_BUILD = "render-gateway-v2"


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _build_drive_store() -> DriveAssetStore | None:
    token_file = os.getenv("CURIOUS_DRIVE_TOKEN_FILE", "").strip()
    artifact_parent_id = os.getenv("CURIOUS_DRIVE_ARTIFACT_PARENT_ID", "").strip()
    if not token_file or not artifact_parent_id:
        return None
    path = Path(token_file).expanduser().resolve()
    if not path.is_file():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        return None
    credentials = Credentials.from_authorized_user_file(str(path))
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return DriveAssetStore(drive_service=service, artifact_parent_id=artifact_parent_id)


def _providers(workspace_root: Path | str):
    workspace = Path(workspace_root).resolve()
    return [
        LocalComfyUIProvider(workspace, legacy_executor=legacy_execute_job),
        GoogleFlowImageProvider(
            authenticated=_env_true("CURIOUS_FLOW_AUTHENTICATED"),
            connector_available=_env_true("CURIOUS_FLOW_CONNECTOR_AVAILABLE"),
            entitlement=os.getenv("CURIOUS_FLOW_ENTITLEMENT", "UNKNOWN"),
            quota=os.getenv("CURIOUS_FLOW_QUOTA", "UNKNOWN"),
        ),
        GoogleFlowVideoProvider(
            authenticated=_env_true("CURIOUS_FLOW_AUTHENTICATED"),
            connector_available=_env_true("CURIOUS_FLOW_CONNECTOR_AVAILABLE"),
            entitlement=os.getenv("CURIOUS_FLOW_ENTITLEMENT", "UNKNOWN"),
            quota=os.getenv("CURIOUS_FLOW_QUOTA", "UNKNOWN"),
        ),
        RunwayProvider(
            authorized=_env_true("CURIOUS_RUNWAY_AUTHORIZED"),
            connector_available=_env_true("CURIOUS_RUNWAY_CONNECTOR_AVAILABLE"),
            entitlement=os.getenv("CURIOUS_RUNWAY_ENTITLEMENT", "UNKNOWN"),
            quota=os.getenv("CURIOUS_RUNWAY_QUOTA", "UNKNOWN"),
        ),
    ]


def _qa_evaluator(job: RenderJob, files: list[Path]) -> dict[str, Any]:
    # V2 intentionally fails closed until a semantic verifier is bound on the worker
    # or the artifact is returned to ChatGPT for review. A completed render alone is
    # never enough to claim FLOW_GRADE verification.
    if job.quality_tier is QualityTier.FLOW_GRADE:
        return {
            "terminal_status": "HUMAN_REVIEW",
            "semantic_verified": False,
            "reason": "No worker-side semantic verifier is bound",
            "artifact_count": len(files),
        }
    return {
        "terminal_status": "ACCEPTED",
        "semantic_verified": False,
        "reason": "non-FLOW local/provider result accepted for configured lower tier",
        "artifact_count": len(files),
    }


def _execute_gateway_job(job: dict[str, Any], workspace_root: Path | str) -> dict[str, Any]:
    render_payload = job["args"].get("render_job") or {}
    try:
        render_job = RenderJob.from_dict(render_payload)
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "message": f"RENDER_GATEWAY contract rejected: {exc}",
            "artifact_manifest": {"gateway_state": "BLOCKED_ASSET"},
        }

    # Explicit compatibility escape hatch only. It is never used as a silent
    # downgrade from FLOW_GRADE.
    if render_job.quality_tier is QualityTier.DRAFT_LOCAL:
        legacy_payload = job["args"].get("legacy_worker_payload")
        if isinstance(legacy_payload, dict):
            result = legacy_execute_job(legacy_payload, workspace_root)
            manifest = dict(result.get("artifact_manifest") or {})
            manifest["gateway_state"] = "DRAFT_LOCAL_COMPAT"
            manifest["quality_tier"] = render_job.quality_tier.value
            result["artifact_manifest"] = manifest
            return result

    drive_store = _build_drive_store()
    orchestrator = RenderOrchestrator(
        providers=_providers(workspace_root),
        asset_store=drive_store,
        qa_evaluator=_qa_evaluator,
        workspace_root=workspace_root,
        chat_attachment_available=False,
    )
    result = orchestrator.run(render_job)
    payload = result.to_dict()
    manifest = {
        "gateway_state": result.state.value,
        "quality_tier": render_job.quality_tier.value,
        "cost_policy": render_job.cost_policy.value,
        "result": payload,
        "auto_purchase": False,
        "silent_quality_downgrade": False,
    }
    if result.return_manifest is not None:
        manifest["return_manifest"] = result.return_manifest.to_dict()

    success = result.state.value == "COMPLETE"
    return {
        "status": "SUCCESS" if success else "BLOCKED",
        "message": result.message,
        "artifact_manifest": manifest,
    }


def execute_job(job: dict[str, Any], workspace_root: Path | str) -> dict[str, Any]:
    validated = validate_job_request(job)
    if validated["job_type"] == "RENDER_GATEWAY":
        return _execute_gateway_job(validated, workspace_root)
    return legacy_execute_job(validated, workspace_root)
