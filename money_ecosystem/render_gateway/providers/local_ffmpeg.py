from __future__ import annotations

from pathlib import Path
import shutil

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


class LocalFFmpegProvider:
    provider_id = "local_ffmpeg"
    mode = ProviderMode.LOCAL

    def preflight(self) -> ProviderStatus:
        available = shutil.which("ffmpeg") is not None
        return ProviderStatus(
            available=available,
            mode=self.mode,
            reason="" if available else "ffmpeg executable not found",
            authorization="LOCAL",
            entitlement="LOCAL",
            quota="UNLIMITED_BY_PROVIDER",
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            max_quality_tier=QualityTier.DRAFT_LOCAL,
            job_types=("VIDEO_RENDER", "FINAL_RENDER"),
            features=("video_assembly", "audio_mux", "frame_sampling", "pan_zoom_parallax"),
            supports_paid_execution=False,
        )

    def estimate(self, job: RenderJob) -> Estimate:
        return Estimate(None, 0.0, "USD", False, True)

    def stage_assets(self, job: RenderJob) -> StagedJob:
        return StagedJob(job=job, metadata={})

    def submit(self, job: StagedJob) -> ProviderJob:
        raise NotImplementedError("FFmpeg assembly execution is wired in the video phase")

    def poll(self, provider_job_id: str) -> ProviderPoll:
        raise NotImplementedError

    def collect(self, provider_job_id: str) -> list[Path]:
        raise NotImplementedError

    def cancel(self, provider_job_id: str) -> None:
        return None
