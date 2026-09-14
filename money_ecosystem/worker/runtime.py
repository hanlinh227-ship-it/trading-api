from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import urllib.error
import urllib.request
from typing import Any

from .allowlist import validate_job_request
from .comfyui_adapter import ComfyUIAdapter, ComfyUIError, DependencyMissing
from .image_package import package_batch
from .image_qa import validate_image
from .image_render_contract import ContractError, ImageRenderJob
from .image_render_executor import SerialImageExecutor
from .image_setup import ImageSetupError, bootstrap_reference_stack
from .image_workflow import WorkflowError, build_sd15_reference_workflow, stage_references

RUNTIME_BUILD = "render-gateway-v2+image-render-v1"
_COMFYUI_BASE = "http://127.0.0.1:8188"
_SUPPORTED_IMAGE_PROFILE = "sd15_reference_lowvram"


def _fetch_json(url: str, timeout: float = 1.5) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _probe_comfyui() -> dict[str, Any]:
    url = _COMFYUI_BASE + "/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return {"available": response.status == 200, "endpoint": url}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"available": False, "endpoint": url}


def _enum_options(node_info: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    required = node_info.get("input", {}).get("required", {})
    if not isinstance(required, dict):
        return out
    for key, spec in required.items():
        if (
            isinstance(spec, list)
            and spec
            and isinstance(spec[0], list)
            and all(isinstance(item, str) for item in spec[0])
        ):
            out[str(key)] = list(spec[0])[:50]
    return out


def _probe_comfyui_reference() -> dict[str, Any]:
    url = _COMFYUI_BASE + "/object_info"
    try:
        objects = _fetch_json(url)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "available": False,
            "endpoint": url,
            "missing": ["ComfyUI object_info"],
            "reason": str(exc),
        }

    required_base = {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
        "LoadImage",
    }
    missing = sorted(name for name in required_base if name not in objects)
    reference_nodes = sorted(name for name in objects if "ipadapter" in name.lower())
    if not reference_nodes:
        missing.append("IPAdapter")

    checkpoint_info = objects.get("CheckpointLoaderSimple", {})
    checkpoint_options = _enum_options(checkpoint_info).get("ckpt_name", [])
    if "CheckpointLoaderSimple" in objects and not checkpoint_options:
        missing.append("SD checkpoint")

    reference_options = {
        name: _enum_options(objects.get(name, {}))
        for name in reference_nodes[:20]
        if _enum_options(objects.get(name, {}))
    }

    return {
        "available": not missing,
        "endpoint": url,
        "missing": missing,
        "checkpoints": checkpoint_options[:20],
        "reference_nodes": reference_nodes[:20],
        "reference_options": reference_options,
    }


def _probe_capabilities(targets: list[str]) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    for target in targets:
        if target == "python":
            capabilities[target] = {"available": True, "version": sys.version.split()[0]}
        elif target == "ffmpeg":
            capabilities[target] = {"available": shutil.which("ffmpeg") is not None}
        elif target == "whisper":
            capabilities[target] = {"available": importlib.util.find_spec("whisper") is not None}
        elif target == "kokoro":
            capabilities[target] = {"available": importlib.util.find_spec("kokoro") is not None}
        elif target == "comfyui":
            capabilities[target] = _probe_comfyui()
        elif target == "comfyui_reference":
            capabilities[target] = _probe_comfyui_reference()
        else:
            capabilities[target] = {"available": False, "reason": "unsupported probe target"}
    return capabilities


def _safe_job_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip()).strip("._")
    return cleaned or "image-job"


def _execute_image_render(job: dict[str, Any], workspace_root: Path | str) -> dict[str, Any]:
    try:
        spec = ImageRenderJob.from_payload(job["args"], workspace_root)
    except (ContractError, TypeError, ValueError, KeyError) as exc:
        return {
            "status": "BLOCKED",
            "message": f"IMAGE_RENDER contract rejected: {exc}",
            "artifact_manifest": {},
        }

    if spec.workflow_profile != _SUPPORTED_IMAGE_PROFILE:
        return {
            "status": "BLOCKED",
            "message": f"IMAGE_RENDER unsupported workflow profile: {spec.workflow_profile}",
            "artifact_manifest": {"zero_paid_services": True, "cloud_fallback": False},
        }

    missing_refs = [str(ref.path) for ref in spec.references if not ref.path.is_file()]
    if missing_refs:
        return {
            "status": "BLOCKED",
            "message": "IMAGE_RENDER missing reference assets: " + ", ".join(missing_refs),
            "artifact_manifest": {
                "missing_references": missing_refs,
                "zero_paid_services": True,
                "cloud_fallback": False,
            },
        }

    adapter = ComfyUIAdapter()
    try:
        preflight = adapter.preflight()
        input_dir = adapter.input_directory()
        staged = stage_references(
            references=[(ref.id, ref.path) for ref in spec.references],
            comfyui_input_dir=input_dir,
            job_id=job["job_id"],
        )
    except (DependencyMissing, WorkflowError) as exc:
        return {
            "status": "BLOCKED",
            "message": f"IMAGE_RENDER dependency/staging blocked: {exc}",
            "artifact_manifest": {"zero_paid_services": True, "cloud_fallback": False},
        }
    except (ComfyUIError, OSError) as exc:
        return {
            "status": "BLOCKED",
            "message": f"IMAGE_RENDER ComfyUI unavailable: {exc}",
            "artifact_manifest": {"zero_paid_services": True, "cloud_fallback": False},
        }

    safe_job = _safe_job_id(job["job_id"])
    workspace = Path(workspace_root).resolve()
    output_root = workspace.parent / "artifacts" / safe_job
    executor = SerialImageExecutor(adapter, output_root)

    def workflow_factory(job_spec, scene, seed):
        names = [staged[reference_id] for reference_id in scene.reference_ids]
        return build_sd15_reference_workflow(
            prompt=scene.prompt,
            reference_input_names=names,
            seed=seed,
            width=job_spec.width,
            height=job_spec.height,
            filename_prefix=f"curious_beyond/{safe_job}/scene_{scene.id:02d}",
        )

    def artifact_fetcher(artifact, target):
        adapter.fetch_artifact(artifact, target)
        qa = validate_image(target, spec.width, spec.height)
        if not qa.accepted:
            raise WorkflowError(f"rendered artifact failed QA: {qa.reason}")

    scene_results = executor.execute(spec, workflow_factory, artifact_fetcher)
    scene_by_id = {scene.id: scene for scene in spec.scenes}
    seen_hashes: set[str] = set()
    records: list[dict[str, Any]] = []

    for result in scene_results:
        scene = scene_by_id[result.scene_id]
        record: dict[str, Any] = {
            "scene_id": result.scene_id,
            "status": result.status,
            "attempts": result.attempts,
            "seed": result.seed,
            "artifact_path": result.artifact_path,
            "error": result.error,
            "prompt": scene.prompt,
            "reference_ids": list(scene.reference_ids),
            "workflow_profile": spec.workflow_profile,
        }
        if result.status == "ACCEPTED" and result.artifact_path:
            qa = validate_image(
                result.artifact_path,
                spec.width,
                spec.height,
                seen_hashes=seen_hashes,
                identity_evidence=None,
            )
            record["qa"] = {
                "accepted": qa.accepted,
                "sha256": qa.sha256,
                "identity_status": qa.identity_status,
                "reason": qa.reason,
            }
            if not qa.accepted:
                record["status"] = "FAILED"
                record["error"] = f"post-render QA failed: {qa.reason}"
        else:
            record["qa"] = {
                "accepted": False,
                "sha256": None,
                "identity_status": "UNVERIFIED",
                "reason": result.error,
            }
        records.append(record)

    package = package_batch(
        job["job_id"],
        records,
        output_root,
        package_name=f"{_safe_job_id(spec.project_id)}_{safe_job}.zip",
    )
    package["scenes"] = records
    package["workflow_profile"] = spec.workflow_profile
    package["reference_nodes"] = preflight.get("reference_nodes", [])
    package["checkpoints"] = preflight.get("checkpoints", [])
    package["cloud_fallback"] = False

    if package["accepted"] == len(records) and records:
        status = "SUCCESS"
        message = f"IMAGE_RENDER completed: {package['accepted']} scene(s) accepted"
    elif package["accepted"] > 0:
        status = "PARTIAL"
        message = f"IMAGE_RENDER partial: {package['accepted']} accepted, {package['failed']} failed"
    else:
        status = "FAILED"
        message = f"IMAGE_RENDER failed: {package['failed']} scene(s) failed"

    return {
        "status": status,
        "message": message,
        "artifact_manifest": package,
    }


def _execute_image_setup(job: dict[str, Any]) -> dict[str, Any]:
    action = job["args"].get("action")
    if action != "bootstrap_reference_stack":
        return {
            "status": "BLOCKED",
            "message": "IMAGE_SETUP only permits bootstrap_reference_stack",
            "artifact_manifest": {"zero_paid_services": True, "cloud_fallback": False},
        }
    try:
        manifest = bootstrap_reference_stack()
    except ImageSetupError as exc:
        return {
            "status": "BLOCKED",
            "message": f"IMAGE_SETUP failed: {exc}",
            "artifact_manifest": {"zero_paid_services": True, "cloud_fallback": False},
        }
    return {
        "status": "SUCCESS",
        "message": "IMAGE_SETUP reference stack installed; ComfyUI restart required",
        "artifact_manifest": manifest,
    }


def _build_render_gateway_orchestrator(workspace_root: Path | str):
    """Build a truthful V2 orchestrator for the Windows worker.

    Cloud providers stay unavailable here until a real authenticated execution
    connector is bound. This is deliberate: the worker must fail closed rather
    than claim Flow-grade capability it cannot execute. Legacy local IMAGE_RENDER
    remains available separately as an explicit DRAFT_LOCAL compatibility path.
    """
    from ..render_gateway.orchestrator import RenderOrchestrator
    from ..render_gateway.providers.google_flow_image import GoogleFlowImageProvider
    from ..render_gateway.providers.google_flow_video import GoogleFlowVideoProvider
    from ..render_gateway.providers.runway import RunwayProvider

    providers = [
        GoogleFlowImageProvider(authenticated=False, connector_available=False),
        GoogleFlowVideoProvider(authenticated=False, connector_available=False),
        RunwayProvider(authorized=False, connector_available=False),
    ]

    def truthful_unverified_qa(_job, _files):
        return {
            "terminal_status": "HUMAN_REVIEW",
            "semantic_verified": False,
            "reason": "No worker-side semantic verifier has been bound yet",
        }

    return RenderOrchestrator(
        providers=providers,
        asset_store=None,
        qa_evaluator=truthful_unverified_qa,
        workspace_root=workspace_root,
        chat_attachment_available=False,
    )


def _execute_render_gateway(job: dict[str, Any], workspace_root: Path | str) -> dict[str, Any]:
    from ..render_gateway.contract import RenderJob
    from ..render_gateway.state import JobState

    try:
        render_job = RenderJob.from_dict(job["args"]["render_job"])
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "status": "BLOCKED",
            "message": f"RENDER_GATEWAY contract rejected: {exc}",
            "artifact_manifest": {},
        }

    if render_job.job_id != job["job_id"]:
        return {
            "status": "BLOCKED",
            "message": "RENDER_GATEWAY outer job_id must match render_job.job_id",
            "artifact_manifest": {},
        }

    try:
        orchestrator = _build_render_gateway_orchestrator(workspace_root)
        result = orchestrator.run(render_job)
    except Exception as exc:
        return {
            "status": "FAILED",
            "message": f"RENDER_GATEWAY orchestration failed: {exc}",
            "artifact_manifest": {
                "quality_tier": render_job.quality_tier.value,
                "auto_purchase": False,
                "silent_quality_downgrade": False,
            },
        }

    if result.state is JobState.COMPLETE:
        status = "SUCCESS"
    elif result.state in {
        JobState.BLOCKED_ASSET,
        JobState.BLOCKED_AUTH,
        JobState.QUALITY_TARGET_UNAVAILABLE,
        JobState.PROVIDER_QUOTA,
        JobState.WORKER_OFFLINE,
    }:
        status = "BLOCKED"
    else:
        status = "FAILED"

    return {
        "status": status,
        "message": result.message,
        "artifact_manifest": {
            "render_gateway": result.to_dict(),
            "quality_tier": render_job.quality_tier.value,
            "auto_purchase": False,
            "silent_quality_downgrade": False,
        },
    }


def execute_job(job: dict[str, Any], workspace_root: Path | str) -> dict[str, Any]:
    job = validate_job_request(job)
    job_type = job["job_type"]

    if job_type == "MEDIA_PROBE":
        targets = job["args"].get("targets") or ["python", "ffmpeg", "whisper", "kokoro", "comfyui"]
        if not isinstance(targets, list) or not all(isinstance(item, str) for item in targets):
            return {"status": "BLOCKED", "message": "Probe targets must be a list of strings", "artifact_manifest": {}}
        capabilities = _probe_capabilities(targets)
        all_available = all(item.get("available") is True for item in capabilities.values()) if capabilities else True
        return {
            "status": "SUCCESS" if all_available else "DEGRADED",
            "message": "Media capability probe completed",
            "artifact_manifest": {"capabilities": capabilities},
        }

    if job_type == "IMAGE_SETUP":
        return _execute_image_setup(job)

    if job_type == "IMAGE_RENDER":
        return _execute_image_render(job, workspace_root)

    if job_type == "RENDER_GATEWAY":
        return _execute_render_gateway(job, workspace_root)

    return {
        "status": "BLOCKED",
        "message": f"{job_type} is not enabled until its dedicated renderer adapter passes verification",
        "artifact_manifest": {},
    }
