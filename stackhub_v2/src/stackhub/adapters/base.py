from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from stackhub.models import Opportunity
from stackhub.source_capabilities import SourceCapabilities


class AdapterError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class ClaimReceipt:
    source: str
    opportunity_id: str
    workspace_reference: str
    expires_at: str | None = None


@dataclass(frozen=True)
class AwardRequestReceipt:
    source: str
    opportunity_id: str
    external_reference: str
    status: str = "PENDING"


@dataclass(frozen=True)
class AwardStatus:
    source: str
    opportunity_id: str
    status: str
    workspace_reference: str | None = None


@dataclass(frozen=True)
class SubmissionReceipt:
    source: str
    opportunity_id: str
    reference: str
    submission_id: str | None = None
    status: str | None = None


class SourceAdapter(Protocol):
    source_name: str
    capabilities: SourceCapabilities

    async def discover(self, limit: int = 50) -> list[Opportunity]: ...


class MutationSourceAdapter(SourceAdapter, Protocol):
    async def claim(self, opportunity_id: str) -> ClaimReceipt: ...

    async def submit(
        self,
        opportunity_id: str,
        artifact_reference: str,
    ) -> SubmissionReceipt: ...


class AwardSourceAdapter(SourceAdapter, Protocol):
    async def request_award(
        self,
        opportunity_id: str,
        message: str,
    ) -> AwardRequestReceipt: ...

    async def poll_award(
        self,
        opportunity_id: str,
        external_reference: str,
    ) -> AwardStatus: ...


# Compatibility alias for the original scanner interface.
OpportunitySource = SourceAdapter
