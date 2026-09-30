from datetime import datetime, timezone
import sqlite3

import pytest

from stackhub.adapters.base import ClaimReceipt, SubmissionReceipt, AwardStatus
from stackhub.orchestrator import RevenueOrchestrator
from stackhub.solvers.base import Artifact, SolverResult
from stackhub.source_capabilities import SourceCapabilities
from stackhub.work_queue import FallbackLane, FallbackWorkQueue

NOW = datetime.now(timezone.utc)


class Repo:
    def __init__(self, rows):
        self.rows = list(rows)
        self.claims = {}
        self.submissions = {}
        self.events = []
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE claims(source TEXT, opportunity_id TEXT, state TEXT)"
        )

    def reserve_next_opportunity(self, source, max_active_claims, reserved_at):
        active = sum(
            1
            for value in self.claims.values()
            if value not in {"PAID", "REJECTED", "EXPIRED", "FAILED_PERMANENT"}
        )
        if active >= max_active_claims or not self.rows:
            return None
        row = self.rows.pop(0)
        self.claims[(row["source"], row["id"])] = "RESERVED"
        self.conn.execute(
            "INSERT INTO claims VALUES(?,?,?)",
            (row["source"], row["id"], "RESERVED"),
        )
        self.conn.commit()
        return {**row, "opportunity_id": row["id"], "state": "RESERVED"}

    def _set(self, source, opportunity_id, state):
        self.claims[(source, opportunity_id)] = state
        self.conn.execute(
            "UPDATE claims SET state=? WHERE source=? AND opportunity_id=?",
            (state, source, opportunity_id),
        )
        self.conn.commit()

    def record_claim(self, source, opportunity_id, reference, now):
        self._set(source, opportunity_id, "CLAIMED")

    def transition_claim(self, source, opportunity_id, target, now, error_code=None):
        self._set(source, opportunity_id, target.value)

    def record_verification_event(self, *args):
        self.events.append(args)

    def record_submission(
        self,
        source,
        opportunity_id,
        reference,
        submission_id,
        now,
    ):
        self.submissions[(source, opportunity_id)] = {
            "reference": reference,
            "submission_id": submission_id,
        }

    def get_claim(self, source, opportunity_id):
        return {"state": self.claims[(source, opportunity_id)]}

    def get_submission(self, source, opportunity_id):
        return self.submissions.get((source, opportunity_id))


class Adapter:
    def __init__(self, name):
        self.source_name = name
        self.capabilities = SourceCapabilities(
            agent_allowed=True,
            auto_claim=True,
            auto_submit=True,
            mutation_verified_at=NOW,
            terms_verified_at=NOW,
        )
        self.claims = 0
        self.submits = 0

    async def claim(self, opportunity_id):
        self.claims += 1
        return ClaimReceipt(
            self.source_name,
            opportunity_id,
            f"workspace:{opportunity_id}",
        )

    async def submit(self, opportunity_id, reference):
        self.submits += 1
        return SubmissionReceipt(
            self.source_name,
            opportunity_id,
            reference,
            f"sub:{opportunity_id}",
            "submitted",
        )


class Solver:
    async def solve(self, opportunity, workspace_reference):
        return SolverResult(
            Artifact(f"https://artifact/{opportunity.id}"),
            {"verified_by": "test"},
        )


class FailingSolver:
    async def solve(self, opportunity, workspace_reference):
        raise RuntimeError("synthetic_solver_failure")


def row(source, opportunity_id, score=1):
    return {
        "source": source,
        "id": opportunity_id,
        "url": f"https://{source}/{opportunity_id}",
        "category": "coding",
        "reward_amount": "10",
        "reward_asset": "USD",
        "reward_network": None,
        "requirements_json": "[]",
        "acceptance_criteria_json": "[]",
        "competition_model": "best",
        "agent_allowed": 1,
        "estimated_effort_minutes": 10,
        "score_usd_per_minute": str(score),
    }


@pytest.mark.asyncio
async def test_orchestrator_switches_sources_and_runs_bounded_batch():
    repo = Repo([row("a", "1"), row("b", "2")])
    a = Adapter("a")
    b = Adapter("b")

    output = await RevenueOrchestrator(
        repo,
        {"a": a, "b": b},
        {"coding": Solver()},
        max_active_claims=2,
    ).run_batch(now=NOW)

    assert {item["source"] for item in output} == {"a", "b"}
    assert all(item["state"] == "SUBMITTED" for item in output)
    assert a.claims == 1
    assert b.claims == 1


@pytest.mark.asyncio
async def test_orchestrator_uses_fallback_when_no_paid_work():
    queue = FallbackWorkQueue()
    called = []

    async def work():
        called.append(1)
        return {"ok": True}

    queue.put(
        "improve-api",
        FallbackLane.PRODUCT_IMPROVEMENT,
        5,
        work,
    )
    output = await RevenueOrchestrator(
        Repo([]),
        {},
        {},
        fallback_queue=queue,
    ).run_batch(now=NOW)

    assert output[0]["state"] == "FALLBACK_COMPLETED"
    assert called == [1]


@pytest.mark.asyncio
async def test_accepted_pending_award_solver_failure_becomes_retryable():
    opportunity = row("taskforce", "canary")
    repo = Repo([])
    repo.rows_by_id = {("taskforce", "canary"): opportunity}
    repo.claims[("taskforce", "canary")] = "PENDING_AWARD"
    repo.conn.execute("INSERT INTO claims VALUES(?,?,?)", ("taskforce", "canary", "PENDING_AWARD"))
    repo.conn.commit()

    def get_active_claims():
        return [{
            "source": "taskforce",
            "opportunity_id": "canary",
            "state": repo.claims[("taskforce", "canary")],
            "clone_url": "application:123",
        }]

    def activate_award(source, opportunity_id, workspace_reference, now):
        repo._set(source, opportunity_id, "CLAIMED")

    def get_opportunity(source, opportunity_id):
        return repo.rows_by_id[(source, opportunity_id)]

    repo.get_active_claims = get_active_claims
    repo.activate_award = activate_award
    repo.get_opportunity = get_opportunity

    class PendingAdapter(Adapter):
        async def poll_award(self, opportunity_id, external_reference):
            return AwardStatus("taskforce", opportunity_id, "ACCEPTED", "task:canary")

    output = await RevenueOrchestrator(
        repo,
        {"taskforce": PendingAdapter("taskforce")},
        {"coding": FailingSolver()},
        max_active_claims=1,
    ).run_batch(now=NOW)

    assert output[0]["state"] == "FAILED_RETRYABLE"
    assert repo.claims[("taskforce", "canary")] == "FAILED_RETRYABLE"
