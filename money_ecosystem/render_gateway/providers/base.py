from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from ..contract import QualityTier, RenderJob


class ProviderMode(str, Enum):
    LOCAL = "LOCAL"
    API = "API"
    CONNECTOR = "CONNECTOR"
    INTERACTIVE = "INTERACTIVE"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class ProviderStatus:
    available: bool
    mode: ProviderMode
    reason: str = ""
    authorization: str = "UNKNOWN"
    entitlement: str = "UNKNOWN"
    quota: str = "UNKNOWN"


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    max_quality_tier: QualityTier
    job_types: tuple[str, ...]
    features: tuple[str, ...]
    supports_paid_execution: bool = False


@dataclass(frozen=True)
class Estimate:
    estimated_seconds: float | None
    estimated_cost: float | None
    currency: str | None = None
    requires_new_paid_credits: bool = False
    covered_by_existing_entitlement: bool | None = None


@dataclass(frozen=True)
class StagedJob:
    job: RenderJob
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProviderJob:
    provider_job_id: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProviderPoll:
    provider_job_id: str
    state: str
    message: str = ""


class RenderProvider(Protocol):
    provider_id: str
    mode: ProviderMode

    def preflight(self) -> ProviderStatus: ...
    def capabilities(self) -> ProviderCapabilities: ...
    def estimate(self, job: RenderJob) -> Estimate: ...
    def stage_assets(self, job: RenderJob) -> StagedJob: ...
    def submit(self, job: StagedJob) -> ProviderJob: ...
    def poll(self, provider_job_id: str) -> ProviderPoll: ...
    def collect(self, provider_job_id: str) -> list[Path]: ...
    def cancel(self, provider_job_id: str) -> None: ...
