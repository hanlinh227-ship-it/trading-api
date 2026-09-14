from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..contract import QualityTier, RenderJob
from .base import (
    Estimate,
    ProviderCapabilities,
    ProviderJob,
    ProviderMode,
    ProviderPoll,
    ProviderStatus,
    StagedJob,
)


class LocalComfyUIProvider:
    """Capability wrapper around the existing local ComfyUI worker path.

    The existing SD1.5 + global-IPAdapter implementation is deliberately
    advertised only as DRAFT_LOCAL. FLOW_GRADE routing must never select it.
    """

    provider_id = "local_comfyui"
    mode = ProviderMode.LOCAL

    def __init__(
        self,
        workspace_root: Path | str,
        *,
        legacy_executor: Callable[[dict[str, Any], Path | str], dict[str, Any]] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._legacy_executor = legacy_executor
        self._results: dict[str, dict[str, Any]] = {}

    def preflight(self) -> ProviderStatus:
        try:
            from money_ecosystem.worker.comfyui_adapter import ComfyUIAdapter

            ComfyUIAdapter().preflight()
            return ProviderStatus(
                True,
                self.mode,
                authorization="LOCAL",
                entitlement="LOCAL",
                quota="GPU_BOUND",
            )
        except Exception as exc:
            return ProviderStatus(
                False,
                self.mode,
                reason=str(exc),
                authorization="LOCAL",
                entitlement="LOCAL",
                quota="UNKNOWN",
            )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            max_quality_tier=QualityTier.DRAFT_LOCAL,
            job_types=("IMAGE_RENDER",),
            features=("image_reference_sd15", "serial_low_vram", "legacy_global_ipadapter"),
            supports_paid_execution=False,
        )

    def estimate(self, job: RenderJob) -> Estimate:
        return Estimate(None, 0.0, "USD", False, True)

    def stage_assets(self, job: RenderJob) -> StagedJob:
        return StagedJob(job=job, metadata={"requires_local_asset_materialization": True})

    def submit(self, job: StagedJob) -> ProviderJob:
        legacy_payload = job.metadata.get("legacy_worker_payload")
        if self._legacy_executor is None or not isinstance(legacy_payload, dict):
            raise RuntimeError(
                "local_comfyui requires a staged legacy_worker_payload; "
                "no silent conversion from FLOW_GRADE/Drive assets is permitted"
            )
        result = self._legacy_executor(legacy_payload, self.workspace_root)
        provider_job_id = f"local:{job.job.job_id}:{job.job.attempt_id}"
        self._results[provider_job_id] = result
        return ProviderJob(provider_job_id, {"synchronous": True})

    def poll(self, provider_job_id: str) -> ProviderPoll:
        result = self._results.get(provider_job_id)
        if result is None:
            return ProviderPoll(provider_job_id, "UNKNOWN", "no local result")
        status = str(result.get("status", "FAILED"))
        return ProviderPoll(provider_job_id, "COMPLETE" if status in {"SUCCESS", "PARTIAL"} else "FAILED", status)

    def collect(self, provider_job_id: str) -> list[Path]:
        result = self._results.get(provider_job_id) or {}
        manifest = result.get("artifact_manifest") or {}
        paths: list[Path] = []
        for scene in manifest.get("scenes", []):
            artifact = scene.get("artifact_path")
            if artifact:
                paths.append(Path(artifact))
        package_path = manifest.get("package_path") or manifest.get("zip_path")
        if package_path:
            paths.append(Path(package_path))
        return paths

    def cancel(self, provider_job_id: str) -> None:
        return None
