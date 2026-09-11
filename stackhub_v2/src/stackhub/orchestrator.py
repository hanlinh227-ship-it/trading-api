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


_ASYNC_COMPETITION = {"application", "bid"}
_RECOVERABLE_ACTIVE_STATES = {
    WorkerState.RESERVED.value,
    WorkerState.PENDING_AWARD.value,
    WorkerState.CLAIMED.value,
    WorkerState.SOLVING.value,
    WorkerState.VERIFIED.value,
}


class RevenueOrchestrator:
    def __init__(self, repo, adapters: Mapping[str, object], solvers: Mapping[str, object], *, max_active_claims: int = 4, fallback_queue: FallbackWorkQueue | None = None):
        self.repo = repo
        self.adapters = dict(adapters)
        self.solvers = dict(solvers)
        self.max_active_claims = max_active_claims
        self.fallback_queue = fallback_queue or FallbackWorkQueue()
        self.submission = SubmissionManager(repo, self.adapters)

    def _opportunity_from_row(self, row: dict[str, object]) -> Opportunity:
        return Opportunity(
            id=str(row["id"]), source=str(row["source"]), url=str(row["url"]), category=str(row["category"]),
            reward=Reward(amount=Decimal(str(row["reward_amount"])), asset=str(row["reward_asset"]), network=row.get("reward_network")),
            deadline=None, requirements=tuple(json.loads(str(row.get("requirements_json") or "[]"))),
            acceptance_criteria=tuple(json.loads(str(row.get("acceptance_criteria_json") or "[]"))),
            competition_model=str(row.get("competition_model") or "unknown"), agent_allowed=bool(row.get("agent_allowed")),
            estimated_effort_minutes=int(row.get("estimated_effort_minutes") or 60),
        )

    def _recover_failure(self, source: str, opportunity_id: str, now: datetime, exc: Exception) -> dict[str, object]:
        error_code = getattr(exc, "error_code", None)
        status_code = getattr(exc, "status_code", None)
        safe_reason = str(error_code or type(exc).__name__)
        if status_code is not None:
            safe_reason = f"{safe_reason}:http_{status_code}"
        row_state=self.repo.conn.execute("SELECT state FROM claims WHERE source=? AND opportunity_id=?",(source,opportunity_id)).fetchone()
        current=None if row_state is None else str(row_state["state"])
        if current in _RECOVERABLE_ACTIVE_STATES:
            try:
                self.repo.transition_claim(source, opportunity_id, WorkerState.FAILED_RETRYABLE, now, safe_reason)
            except Exception:
                pass
        return {"state":"FAILED_RETRYABLE","source":source,"opportunity_id":opportunity_id,"reason":safe_reason}

    async def _solve_claimed(self, row: dict[str, object], workspace_reference: str, now: datetime) -> dict[str, object]:
        source=str(row["source"]); opportunity_id=str(row["id"])
        self.repo.transition_claim(source, opportunity_id, WorkerState.SOLVING, now)
        opportunity=self._opportunity_from_row(row)
        solver=self.solvers.get(opportunity.category) or self.solvers.get("service")
        if solver is None:
            raise RuntimeError("solver_missing")
        result=await solver.solve(opportunity, workspace_reference)
        verification=verify_solver_result(result)
        self.repo.record_verification_event(source, opportunity_id, f"artifact_verification:{'pass' if verification.passed else 'fail'}:{verification.reason or 'ok'}", now)
        if not verification.passed:
            self.repo.transition_claim(source, opportunity_id, WorkerState.FAILED_PERMANENT, now, verification.reason)
            return {"state":"FAILED_PERMANENT","source":source,"opportunity_id":opportunity_id,"reason":verification.reason}
        self.repo.transition_claim(source, opportunity_id, WorkerState.VERIFIED, now)
        submission=await self.submission.submit_verified(source, opportunity_id, result.artifact, now)
        return {"state":"SUBMITTED","source":source,"opportunity_id":opportunity_id,"submission_id":submission.submission_id,"reference":submission.reference}

    async def _process_reserved(self, row: dict[str, object], now: datetime) -> dict[str, object]:
        source=str(row["source"]); opportunity_id=str(row["opportunity_id"]); adapter=self.adapters.get(source)
        if adapter is None:
            self.repo.transition_claim(source, opportunity_id, WorkerState.FAILED_RETRYABLE, now, "adapter_missing")
            return {"state":"FAILED_RETRYABLE","source":source,"opportunity_id":opportunity_id,"reason":"adapter_missing"}
        try:
            assert_source_eligible_for("claim", adapter.capabilities)
            competition=str(row.get("competition_model") or "").lower()
            if competition in _ASYNC_COMPETITION and hasattr(adapter, "request_award"):
                receipt=await adapter.request_award(opportunity_id, "Autonomous agent ready to complete this task. I will follow the stated requirements, validate the deliverable before submission, and provide concise evidence of completion.")
                self.repo.record_pending_award(source, opportunity_id, receipt.external_reference, now)
                return {"state":"PENDING_AWARD","source":source,"opportunity_id":opportunity_id,"external_reference":receipt.external_reference}
            receipt=await adapter.claim(opportunity_id)
            self.repo.record_claim(source, opportunity_id, receipt.workspace_reference, now)
            return await self._solve_claimed(row, receipt.workspace_reference, now)
        except Exception as exc:
            return self._recover_failure(source, opportunity_id, now, exc)

    async def _reconcile_pending(self, now: datetime) -> list[dict[str, object]]:
        output=[]
        getter=getattr(self.repo, "get_active_claims", None)
        if getter is None:
            return output
        for claim in getter():
            if str(claim.get("state")) != WorkerState.PENDING_AWARD.value:
                continue
            source=str(claim["source"]); opportunity_id=str(claim["opportunity_id"]); adapter=self.adapters.get(source)
            if adapter is None or not hasattr(adapter,"poll_award"):
                continue
            try:
                status=await adapter.poll_award(opportunity_id, str(claim.get("clone_url") or ""))
                normalized=str(status.status).upper()
                if normalized in {"ACCEPTED","ASSIGNED","WON"}:
                    workspace=status.workspace_reference or str(claim.get("clone_url") or opportunity_id)
                    self.repo.activate_award(source, opportunity_id, workspace, now)
                    row=self.repo.get_opportunity(source, opportunity_id)
                    if row is None: raise RuntimeError("opportunity_missing")
                    output.append(await self._solve_claimed(row, workspace, now))
                elif normalized in {"REJECTED","LOST"}:
                    self.repo.transition_claim(source, opportunity_id, WorkerState.REJECTED, now)
                    output.append({"state":"REJECTED","source":source,"opportunity_id":opportunity_id})
                else:
                    output.append({"state":"PENDING_AWARD","source":source,"opportunity_id":opportunity_id})
            except Exception as exc:
                output.append(self._recover_failure(source, opportunity_id, now, exc))
        return output

    async def run_batch(self, *, now: datetime | None = None) -> list[dict[str, object]]:
        now=now or datetime.now(timezone.utc)
        reconciled=await self._reconcile_pending(now)
        if reconciled:
            return reconciled
        reserved=[]
        for _ in range(self.max_active_claims):
            row=self.repo.reserve_next_opportunity(None,self.max_active_claims,now)
            if row is None: break
            reserved.append(row)
        if reserved:
            return list(await asyncio.gather(*(self._process_reserved(row,now) for row in reserved)))
        fallback=self.fallback_queue.pop()
        if fallback is None: return [{"state":"IDLE","reason":"no_paid_or_fallback_work"}]
        result=await fallback.handler()
        return [{"state":"FALLBACK_COMPLETED","name":fallback.name,"lane":fallback.lane.value,"result":result}]