from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from stackhub.adapters.taskbounty import TaskAccess, SubmissionResult
from stackhub.config import RuntimeConfig, SourceConfig
from stackhub.models import Opportunity, Reward
from stackhub.policy import PolicyDecision
from stackhub.repository import StackHubRepository
from stackhub.scoring import ScoreResult
from stackhub.verification import VerificationEvidence
from stackhub.worker import TaskBountyWorker


def live_config():
    return RuntimeConfig(
        dry_run=False,
        worker_enabled=True,
        external_spend_limit_usd=Decimal("0"),
        scan_interval_seconds=300,
        max_concurrent_tasks=1,
        max_active_claims=1,
        sources={
            "taskbounty": SourceConfig(
                enabled=True,
                base_url="https://www.task-bounty.com/api/v1",
                agent_native=True,
                read_only=False,
                request_timeout_seconds=20,
                min_poll_interval_seconds=60,
            )
        },
    )


def seed_opportunity(repo: StackHubRepository):
    item = Opportunity(
        id="tb-1",
        source="taskbounty",
        url="https://github.com/acme/repo/issues/1",
        category="coding",
        reward=Reward(amount=Decimal("40"), asset="USD", network=None),
        deadline=None,
        requirements=("Fix bug",),
        acceptance_criteria=("Tests pass",),
        competition_model="best_submission",
        agent_allowed=True,
        estimated_effort_minutes=30,
    )
    repo.upsert_opportunity(
        item,
        PolicyDecision(allowed=True, reasons=()),
        ScoreResult(expected_net_value_usd=Decimal("16"), score_usd_per_minute=Decimal("0.53")),
    )


class FakeAdapter:
    def __init__(self):
        self.accessed = []
        self.submitted = []

    async def access_task(self, task_id: str):
        self.accessed.append(task_id)
        return TaskAccess(task_id=task_id, clone_url="https://clone.invalid/repo", expires_at=None)

    async def submit_pr(self, task_id: str, external_link: str):
        self.submitted.append((task_id, external_link))
        return SubmissionResult(id="sub-1", task_id=task_id, status="verifying", external_link=external_link)


@pytest.mark.asyncio
async def test_worker_accesses_verifies_and_submits_one_task(tmp_path: Path):
    repo = StackHubRepository(tmp_path / "stackhub.db")
    repo.initialize()
    seed_opportunity(repo)
    adapter = FakeAdapter()

    async def solver(task_id: str, clone_url: str, issue_url: str):
        assert task_id == "tb-1"
        assert clone_url.startswith("https://clone.invalid")
        return (
            "https://github.com/acme/repo/pull/7",
            VerificationEvidence(
                test_command=("pytest",),
                exit_code=0,
                stdout_tail="1 passed",
                stderr_tail="",
                diff_path="/tmp/fix.patch",
                passed=True,
            ),
        )

    worker = TaskBountyWorker(live_config(), repo, adapter, solver=solver)
    result = await worker.run_once(now=datetime.now(timezone.utc))

    assert result["state"] == "SUBMITTED"
    assert adapter.accessed == ["tb-1"]
    assert adapter.submitted == [("tb-1", "https://github.com/acme/repo/pull/7")]
    assert len(repo.get_active_claims()) == 1
    repo.close()


@pytest.mark.asyncio
async def test_worker_never_submits_failed_verification(tmp_path: Path):
    repo = StackHubRepository(tmp_path / "stackhub.db")
    repo.initialize()
    seed_opportunity(repo)
    adapter = FakeAdapter()

    async def solver(task_id: str, clone_url: str, issue_url: str):
        return (
            "https://github.com/acme/repo/pull/7",
            VerificationEvidence(("pytest",), 1, "", "failed", "/tmp/fix.patch", False),
        )

    worker = TaskBountyWorker(live_config(), repo, adapter, solver=solver)
    result = await worker.run_once(now=datetime.now(timezone.utc))

    assert result["state"] == "FAILED"
    assert adapter.submitted == []
    assert repo.get_active_claims() == []
    repo.close()
