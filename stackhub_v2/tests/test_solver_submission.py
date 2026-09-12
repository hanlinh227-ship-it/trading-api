from datetime import datetime, timezone

import pytest

from stackhub.adapters.base import SubmissionReceipt
from stackhub.solvers.base import Artifact, SolverResult
from stackhub.source_capabilities import SourceCapabilities
from stackhub.submission import SubmissionManager
from stackhub.verification_gate import verify_solver_result

NOW = datetime.now(timezone.utc)


class Repo:
    def __init__(self, state="VERIFIED"):
        self.claim = {"state": state}
        self.submission = None
        self.transitions = []

    def get_claim(self, *args):
        return self.claim

    def get_submission(self, *args):
        return self.submission

    def record_submission(
        self,
        source,
        opportunity_id,
        reference,
        submission_id,
        observed_at,
    ):
        self.submission = {
            "reference": reference,
            "submission_id": submission_id,
            "status": "submitted",
        }

    def transition_claim(self, source, opportunity_id, target, observed_at):
        self.claim = {"state": target.value}
        self.transitions.append(target.value)


class Adapter:
    capabilities = SourceCapabilities(
        agent_allowed=True,
        auto_submit=True,
        terms_verified_at=NOW,
        mutation_verified_at=NOW,
    )

    def __init__(self):
        self.calls = 0

    async def submit(self, opportunity_id, artifact_reference):
        self.calls += 1
        return SubmissionReceipt(
            "x",
            opportunity_id,
            artifact_reference,
            "sub-1",
            "submitted",
        )


def test_generic_verification_requires_evidence_and_blocks_secrets():
    assert verify_solver_result(SolverResult(Artifact("ref"), {})).passed is False
    assert verify_solver_result(
        SolverResult(Artifact("ref"), {"tests": "ok"})
    ).passed is True
    assert verify_solver_result(
        SolverResult(Artifact("ref"), {"note": "private key: ABC"})
    ).passed is False


@pytest.mark.asyncio
async def test_submission_requires_verified_state():
    repo = Repo("SOLVING")
    adapter = Adapter()
    manager = SubmissionManager(repo, {"x": adapter})

    with pytest.raises(ValueError):
        await manager.submit_verified("x", "1", Artifact("ref"), NOW)

    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_submission_is_idempotent_after_first_receipt():
    repo = Repo()
    adapter = Adapter()
    manager = SubmissionManager(repo, {"x": adapter})

    one = await manager.submit_verified("x", "1", Artifact("https://artifact"), NOW)
    two = await manager.submit_verified("x", "1", Artifact("https://artifact"), NOW)

    assert one.reference == two.reference
    assert adapter.calls == 1
    assert repo.transitions == ["SUBMITTED"]
