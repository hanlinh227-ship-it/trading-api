from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Mapping

from .adapters.base import OpportunitySource
from .adapters.taskbounty import TaskBountyProtocolError
from .config import RuntimeConfig
from .policy import evaluate_opportunity
from .repository import StackHubRepository
from .scoring import ScoreInputs, score_opportunity


@dataclass(frozen=True)
class ScanResult:
    discovered: int = 0
    allowed: int = 0
    denied: int = 0
    errors: int = 0
    retry_after_seconds: int | None = None
    source_outage: bool = False


class Scanner:
    def __init__(
        self,
        config: RuntimeConfig,
        repository: StackHubRepository,
        adapters: Mapping[str, OpportunitySource],
        *,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        if not config.dry_run or config.external_spend_limit_usd != Decimal("0"):
            raise ValueError("Scanner requires strict dry-run zero-spend configuration")
        self.config = config
        self.repository = repository
        self.adapters = dict(adapters)
        self.sleeper = sleeper

    async def run_once(self) -> ScanResult:
        discovered = allowed = denied = errors = 0
        retry_after_seconds: int | None = None
        source_outage = False
        now = datetime.now(timezone.utc)
        for source_name, adapter in self.adapters.items():
            source_cfg = self.config.sources.get(source_name)
            if source_cfg is None or not source_cfg.enabled:
                continue
            try:
                opportunities = await adapter.fetch_open(limit=50)
                self.repository.record_source_health(source_name, True, 200, None, now)
            except TaskBountyProtocolError as exc:
                error_code = exc.error_code or "protocol_error"
                self.repository.record_source_health(source_name, False, exc.status_code, error_code, now)
                errors += 1
                if exc.status_code == 429:
                    retry_after_seconds = max(
                        retry_after_seconds or 0,
                        exc.retry_after_seconds or source_cfg.min_poll_interval_seconds,
                    )
                elif error_code not in {"auth_required", "auth_invalid"}:
                    source_outage = True
                continue
            except Exception:
                self.repository.record_source_health(source_name, False, None, "unexpected_error", now)
                errors += 1
                source_outage = True
                continue

            for opportunity in opportunities:
                discovered += 1
                decision = evaluate_opportunity(opportunity, self.config)
                if decision.allowed:
                    allowed += 1
                    score = score_opportunity(
                        opportunity,
                        ScoreInputs(
                            payout_value_usd=opportunity.reward.amount,
                            win_probability=Decimal("0.35"),
                            verification_probability=Decimal("0.75"),
                            model_cost_usd=Decimal("0"),
                            compute_cost_usd=Decimal("0"),
                            chain_fee_usd=Decimal("0"),
                            expected_failed_work_cost_usd=Decimal("0"),
                        ),
                    )
                else:
                    denied += 1
                    score = None
                self.repository.upsert_opportunity(opportunity, decision, score)
        return ScanResult(
            discovered=discovered,
            allowed=allowed,
            denied=denied,
            errors=errors,
            retry_after_seconds=retry_after_seconds,
            source_outage=source_outage,
        )

    async def run_forever(self, stop_event: asyncio.Event | None = None) -> None:
        stop_event = stop_event or asyncio.Event()
        outage_attempt = 0
        while not stop_event.is_set():
            result = await self.run_once()
            if result.retry_after_seconds is not None:
                outage_attempt = 0
                configured_minimum = max(
                    (source.min_poll_interval_seconds for source in self.config.sources.values() if source.enabled),
                    default=60,
                )
                delay = max(configured_minimum, result.retry_after_seconds)
            elif result.source_outage:
                outage_attempt += 1
                delay = min(60 * (2 ** (outage_attempt - 1)), 900)
            else:
                outage_attempt = 0
                delay = self.config.scan_interval_seconds
            await self.sleeper(delay)
