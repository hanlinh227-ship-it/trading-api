from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .adapters.base import AdapterError, SourceAdapter
from .models import Opportunity
from .source_capabilities import assert_source_eligible_for


class OpportunityPool(Protocol):
    def ingest(self, opportunity: Opportunity) -> None: ...

    def record_source_health(
        self,
        source: str,
        ok: bool,
        status_code: int | None,
        error_code: str | None,
        observed_at: datetime,
    ) -> None: ...


@dataclass(frozen=True)
class ScoutResult:
    source: str
    discovered: int = 0
    errors: int = 0
    retry_after_seconds: int | None = None


class Scout:
    """Read-only source scout. It has no claim/submit path by design."""

    def __init__(self, adapter: SourceAdapter, pool: OpportunityPool):
        assert_source_eligible_for("discover", adapter.capabilities)
        self.adapter = adapter
        self.pool = pool

    async def run_once(self, limit: int = 50) -> ScoutResult:
        now = datetime.now(timezone.utc)
        try:
            items = await self.adapter.discover(limit=limit)
        except AdapterError as exc:
            self.pool.record_source_health(
                self.adapter.source_name,
                False,
                exc.status_code,
                exc.error_code or "adapter_error",
                now,
            )
            return ScoutResult(
                self.adapter.source_name,
                errors=1,
                retry_after_seconds=exc.retry_after_seconds,
            )
        except Exception:
            self.pool.record_source_health(
                self.adapter.source_name,
                False,
                None,
                "unexpected_error",
                now,
            )
            return ScoutResult(self.adapter.source_name, errors=1)

        for item in items:
            self.pool.ingest(item)
        self.pool.record_source_health(self.adapter.source_name, True, 200, None, now)
        return ScoutResult(self.adapter.source_name, discovered=len(items))
