from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from .models import Opportunity, Reward
from .source_capabilities import assert_source_eligible_for
from .submission import SubmissionManager
from .verification_gate import verify_solver_result
from .worker_state import WorkerState
from .work_queue import FallbackWorkQueue


class RevenueOrchestrator:
    def __init__(
        self,
        repo,
        adapters: Mapping[str, object],
        solvers: Mapping[str, object],
        *,
        max_active_claims: int = 4,
        fallback_queue: FallbackWorkQueue | None = None,
    ):
        self.repo = repo
        self.adapters = dict(adapters)
        self.solvers = dict(solvers)
        self.max_active_claims = max_active_claims
        self.fallback_queue = fallback_queue or FallbackWorkQueue()
        self.submission = SubmissionManager(repo, self.adapters)

    def _opportunity_from_row(self, row: dict[str, object]) -> Opportunity:
        return Opportunity(
            id=str(row["id"]),
            source=str(row["source"]),
            url=str(row["url"]),
            category=str(row["category"]),
            reward=Reward(
                amount=Decimal(str(row["reward_amount"])),
                asset=str(row["reward_asset"]),
                network=row.get("reward_network"),
            ),
            deadline=None,
            requirements=tuple(
                json.loads(str(row.get("requirements_json") or "[]"))
            ),
            acceptance_criteria=tuple(
                json.loads(str(row.get("acceptance_criteria_json") or "[]"))
            ),
            competition_model=str(row.get("competition_model") or "unknown"),
            agent_allowed=bool(row.get("agent_allowed")),
            estimated_effort_minutes=int(
                row.get("estimated_effort_minutes") or 60
            ),
        )

    async def _process_reserved(
        self,
        row: dict[str, object],
        now: datetime,
    ) -> dict[str, object]:
        source = str(row["source"])
        opportunity_id = str(row["opportunity_id"])
        adapter = self.adapters.get(source)
        if adapter is None:
            self.repo.transition_claim(
                source,
                opportunity_id,
                WorkerState.FAILED_RETRYABLE,
                now,
                "adapter_missing",
            )
            return {
                "state": "FAILED_RETRYABLE",
                "source": source,
                "opportunity_id": opportunity_id,
                "reason": "adapter_missing",
            }

        try:
            assert_source_eligible_for("claim", adapter.capabilities)
            receipt = await adapter.claim(opportunity_id)
            self.repo.record_claim(
                source,
                opportunity_id,
                receipt.workspace_reference,
                now,
            )
            self.repo.transition_claim(
                source,
                opportunity_id,
                WorkerState.SOLVING,
                now,
            )
            opportunity = self._opportunity_from_row(row)
            solver = self.solvers.get(opportunity.category)
            if solver is None:
                raise RuntimeError("solver_missing")

            result = await solver.solve(opportunity, receipt.workspace_reference)
            verification = verify_solver_result(result)
            self.repo.record_verification_event(
                source,
                opportunity_id,
                f"artifact_verification:{'pass' if verification.passed else 'fail'}:{verification.reason or 'ok'}",
                now,
            )
            if not verification.passed:
                self.repo.transition_claim(
                    source,
                    opportunity_id,
                    WorkerState.FAILED_PERMANENT,
                    now,
                    verification.reason,
                )
                return {
                    "state": "FAILED_PERMANENT",
                    "source": source,
                    "opportunity_id": opportunity_id,
                    "reason": verification.reason,
                }

            self.repo.transition_claim(
                source,
                opportunity_id,
                WorkerState.VERIFIED,
                now,
            )
            submission = await self.submission.submit_verified(
                source,
                opportunity_id,
                result.artifact,
                now,
            )
            return {
                "state": "SUBMITTED",
                "source": source,
                "opportunity_id": opportunity_id,
                "submission_id": submission.submission_id,
                "reference": submission.reference,
            }
        except Exception as exc:
            row_state = self.repo.conn.execute(
                "SELECT state FROM claims WHERE source=? AND opportunity_id=?",
                (source, opportunity_id),
            ).fetchone()
            current = None if row_state is None else str(row_state["state"])
            if current in {
                WorkerState.RESERVED.value,
                WorkerState.CLAIMED.value,
                WorkerState.SOLVING.value,
                WorkerState.VERIFIED.value,
            }:
                try:
                    self.repo.transition_claim(
                        source,
                        opportunity_id,
                        WorkerState.FAILED_RETRYABLE,
                        now,
                        type(exc).__name__,
                    )
                except Exception:
                    pass
            return {
                "state": "FAILED_RETRYABLE",
                "source": source,
                "opportunity_id": opportunity_id,
                "reason": type(exc).__name__,
            }

    async def run_batch(
        self,
        *,
        now: datetime | None = None,
    ) -> list[dict[str, object]]:
        now = now or datetime.now(timezone.utc)
        reserved: list[dict[str, object]] = []
        for _ in range(self.max_active_claims):
            row = self.repo.reserve_next_opportunity(
                None,
                self.max_active_claims,
                now,
            )
            if row is None:
                break
            reserved.append(row)

        if reserved:
            return list(
                await asyncio.gather(
                    *(self._process_reserved(row, now) for row in reserved)
                )
            )

        fallback = self.fallback_queue.pop()
        if fallback is None:
            return [{"state": "IDLE", "reason": "no_paid_or_fallback_work"}]
        result = await fallback.handler()
        return [
            {
                "state": "FALLBACK_COMPLETED",
                "name": fallback.name,
                "lane": fallback.lane.value,
                "result": result,
            }
        ]
