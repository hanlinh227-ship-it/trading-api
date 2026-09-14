from __future__ import annotations

from pathlib import Path

from ..contract import QualityTier, RenderJob
from .base import Estimate, ProviderCapabilities, ProviderJob, ProviderMode, ProviderPoll, ProviderStatus, StagedJob


class ProviderExecutionUnavailable(RuntimeError):
    pass


class RunwayProvider:
    provider_id = "runway"

    def __init__(
        self,
        *,
        authorized: bool,
        connector_available: bool,
        entitlement: str = "UNKNOWN",
        quota: str = "UNKNOWN",
    ) -> None:
        self.authorized = authorized
        self.connector_available = connector_available
        self._entitlement = entitlement
        self._quota = quota
        self.mode = ProviderMode.CONNECTOR if authorized and connector_available else ProviderMode.DISABLED

    def preflight(self) -> ProviderStatus:
        ready = self.authorized and self.connector_available
        return ProviderStatus(
            available=ready,
            mode=self.mode,
            reason="ready" if ready else "Runway connector is not authorized for autonomous execution",
            authorization="AUTHENTICATED" if self.authorized else "BLOCKED_AUTH",
            entitlement=self._entitlement,
            quota=self._quota,
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            max_quality_tier=QualityTier.HIGH,
            job_types=("IMAGE_RENDER", "VIDEO_RENDER"),
            features=("image_to_video", "video_edit", "reference_image", "motion_control"),
            supports_paid_execution=True,
        )

    def estimate(self, job: RenderJob) -> Estimate:
        return Estimate(None, None, requires_new_paid_credits=False, covered_by_existing_entitlement=None)

    def _require_ready(self) -> None:
        if not self.preflight().available:
            raise ProviderExecutionUnavailable(self.preflight().reason)

    def stage_assets(self, job: RenderJob) -> StagedJob:
        self._require_ready()
        return StagedJob(job=job, metadata={"provider": self.provider_id})

    def submit(self, job: StagedJob) -> ProviderJob:
        self._require_ready()
        raise ProviderExecutionUnavailable("Runway execution connector has not been bound to this adapter yet")

    def poll(self, provider_job_id: str) -> ProviderPoll:
        raise ProviderExecutionUnavailable("Runway execution connector has not been bound to this adapter yet")

    def collect(self, provider_job_id: str) -> list[Path]:
        raise ProviderExecutionUnavailable("Runway execution connector has not been bound to this adapter yet")

    def cancel(self, provider_job_id: str) -> None:
        raise ProviderExecutionUnavailable("Runway execution connector has not been bound to this adapter yet")
