from datetime import datetime, timezone

import pytest

from stackhub.repository import StackHubRepository
from stackhub.worker_state import WorkerState, assert_transition


def test_worker_state_allows_forward_transitions():
    assert_transition(WorkerState.DISCOVERED, WorkerState.ELIGIBLE)
    assert_transition(WorkerState.ELIGIBLE, WorkerState.ACCESSED)
    assert_transition(WorkerState.ACCESSED, WorkerState.SOLVING)
    assert_transition(WorkerState.SOLVING, WorkerState.VERIFIED)
    assert_transition(WorkerState.VERIFIED, WorkerState.SUBMITTED)


def test_worker_state_rejects_backward_transition():
    with pytest.raises(ValueError):
        assert_transition(WorkerState.SUBMITTED, WorkerState.SOLVING)


def test_repository_claim_is_idempotent_and_limits_active_claims(tmp_path):
    repo = StackHubRepository(tmp_path / "state.db")
    repo.initialize()
    now = datetime.now(timezone.utc)

    repo.record_claim("taskbounty", "tb-1", "https://clone/one", now)
    repo.record_claim("taskbounty", "tb-1", "https://clone/one", now)
    active = repo.get_active_claims()
    assert len(active) == 1
    assert active[0]["opportunity_id"] == "tb-1"

    with pytest.raises(RuntimeError):
        repo.record_claim("taskbounty", "tb-2", "https://clone/two", now)
    repo.close()


def test_repository_submission_is_idempotent(tmp_path):
    repo = StackHubRepository(tmp_path / "state.db")
    repo.initialize()
    now = datetime.now(timezone.utc)
    repo.record_claim("taskbounty", "tb-1", "https://clone/one", now)
    repo.record_submission("taskbounty", "tb-1", "https://github.com/acme/repo/pull/7", "sub-1", now)
    repo.record_submission("taskbounty", "tb-1", "https://github.com/acme/repo/pull/7", "sub-1", now)

    rows = repo.conn.execute("SELECT * FROM submissions WHERE source=? AND opportunity_id=?", ("taskbounty", "tb-1")).fetchall()
    assert len(rows) == 1
    repo.close()
