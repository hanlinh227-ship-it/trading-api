from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol

from .config import RuntimeConfig
from .repository import StackHubRepository
from .verification import VerificationEvidence


class MutationAdapter(Protocol):
    async def access_task(self, task_id: str): ...
    async def submit_pr(self, task_id: str, external_link: str): ...


Solver = Callable[[str, str, str], Awaitable[tuple[str, VerificationEvidence]]]


class TaskBountyWorker:
    def __init__(
        self,
        config: RuntimeConfig,
        repo: StackHubRepository,
        adapter: MutationAdapter,
        *,
        solver: Solver,
    ):
        if not config.worker_enabled or config.dry_run:
            raise ValueError("TaskBountyWorker requires worker_enabled=true and dry_run=false")
        if config.external_spend_limit_usd != 0:
            raise ValueError("TaskBountyWorker requires zero external spend")
        source = config.sources.get("taskbounty")
        if source is None or source.read_only:
            raise ValueError("TaskBounty mutation source is not enabled")
        self.config = config
        self.repo = repo
        self.adapter = adapter
        self.solver = solver

    def _select_candidate(self) -> dict[str, object] | None:
        active_ids = {str(row["opportunity_id"]) for row in self.repo.get_active_claims()}
        for row in self.repo.list_ranked_opportunities(limit=100):
            if row["source"] != "taskbounty":
                continue
            if not bool(row["policy_allowed"]):
                continue
            if str(row["id"]) in active_ids:
                continue
            return row
        return None

    async def run_once(self, *, now: datetime | None = None) -> dict[str, object]:
        now = now or datetime.now(timezone.utc)
        if self.repo.get_active_claims():
            return {"state": "IDLE", "reason": "active_claim_exists"}

        candidate = self._select_candidate()
        if candidate is None:
            return {"state": "IDLE", "reason": "no_eligible_opportunity"}

        task_id = str(candidate["id"])
        issue_url = str(candidate["url"])

        access = await self.adapter.access_task(task_id)
        self.repo.record_claim("taskbounty", task_id, access.clone_url, now)
        self.repo.update_claim_state("taskbounty", task_id, "SOLVING")

        try:
            pr_url, evidence = await self.solver(task_id, access.clone_url, issue_url)
        except Exception as exc:
            self.repo.record_verification_event("taskbounty", task_id, f"solver_error:{type(exc).__name__}", now)
            self.repo.update_claim_state("taskbounty", task_id, "FAILED")
            return {"state": "FAILED", "task_id": task_id, "reason": "solver_error"}

        self.repo.record_verification_event(
            "taskbounty",
            task_id,
            f"tests_exit={evidence.exit_code};passed={str(evidence.passed).lower()}",
            now,
        )
        if not evidence.passed:
            self.repo.update_claim_state("taskbounty", task_id, "FAILED")
            return {"state": "FAILED", "task_id": task_id, "reason": "verification_failed"}

        self.repo.update_claim_state("taskbounty", task_id, "VERIFIED")
        submission = await self.adapter.submit_pr(task_id, pr_url)
        self.repo.record_submission("taskbounty", task_id, submission.external_link, submission.id, now)
        self.repo.update_claim_state("taskbounty", task_id, "SUBMITTED")
        return {
            "state": "SUBMITTED",
            "task_id": task_id,
            "submission_id": submission.id,
            "status": submission.status,
            "external_link": submission.external_link,
        }
