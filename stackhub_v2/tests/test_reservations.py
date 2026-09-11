from datetime import datetime, timezone

import pytest

from stackhub.repository import StackHubRepository
from stackhub.worker_state import WorkerState


def _seed(repo, source: str, opportunity_id: str, score: float, allowed: int = 1) -> None:
    repo.conn.execute(
        """
        INSERT INTO opportunities(
            source,id,url,category,reward_amount,reward_asset,
            requirements_json,acceptance_criteria_json,competition_model,
            policy_allowed,policy_reasons_json,score_usd_per_minute
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            source,
            opportunity_id,
            "https://example.invalid/job",
            "code",
            "10",
            "USD",
            "[]",
            "[]",
            "claim",
            allowed,
            "[]",
            str(score),
        ),
    )
    repo.conn.commit()


def test_reserve_next_is_unique(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 2)
    _seed(repo, "source-a", "a-2", 1)
    now = datetime.now(timezone.utc)

    first = repo.reserve_next_opportunity(None, 2, now)
    second = repo.reserve_next_opportunity(None, 2, now)

    assert first is not None and second is not None
    assert first["opportunity_id"] != second["opportunity_id"]


def test_reservation_honors_global_capacity_across_sources(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 2)
    _seed(repo, "source-b", "b-1", 3)
    now = datetime.now(timezone.utc)

    assert repo.reserve_next_opportunity(None, 1, now) is not None
    assert repo.reserve_next_opportunity(None, 1, now) is None


def test_source_filter_is_optional(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 1)
    _seed(repo, "source-b", "b-1", 9)
    now = datetime.now(timezone.utc)

    selected = repo.reserve_next_opportunity("source-a", 2, now)
    assert selected is not None
    assert selected["source"] == "source-a"


def test_terminal_claim_stops_counting_as_active(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 2)
    _seed(repo, "source-b", "b-1", 1)
    now = datetime.now(timezone.utc)

    first = repo.reserve_next_opportunity(None, 1, now)
    assert first is not None
    source = str(first["source"])
    opportunity_id = str(first["opportunity_id"])
    for state in (
        WorkerState.CLAIMED,
        WorkerState.SOLVING,
        WorkerState.VERIFIED,
        WorkerState.SUBMITTED,
        WorkerState.PAID,
    ):
        repo.transition_claim(source, opportunity_id, state, now)

    assert repo.reserve_next_opportunity(None, 1, now) is not None


def test_failed_retryable_does_not_consume_capacity_and_can_be_reserved_again(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 10)
    _seed(repo, "source-b", "b-1", 1)
    now = datetime.now(timezone.utc)

    first = repo.reserve_next_opportunity(None, 1, now)
    assert first is not None
    assert first["opportunity_id"] == "a-1"
    repo.transition_claim("source-a", "a-1", WorkerState.FAILED_RETRYABLE, now, "temporary")

    retry = repo.reserve_next_opportunity(None, 1, now)
    assert retry is not None
    assert retry["source"] == "source-a"
    assert retry["opportunity_id"] == "a-1"
    claim = repo.get_claim("source-a", "a-1")
    assert claim is not None
    assert claim["state"] == WorkerState.RESERVED.value
    assert claim["last_error_code"] is None


def test_illegal_backward_and_terminal_resurrection_fail(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 2)
    now = datetime.now(timezone.utc)

    assert repo.reserve_next_opportunity(None, 1, now) is not None
    with pytest.raises(ValueError):
        repo.transition_claim("source-a", "a-1", WorkerState.ELIGIBLE, now)

    for state in (
        WorkerState.CLAIMED,
        WorkerState.SOLVING,
        WorkerState.VERIFIED,
        WorkerState.SUBMITTED,
        WorkerState.REJECTED,
    ):
        repo.transition_claim("source-a", "a-1", state, now)

    with pytest.raises(ValueError):
        repo.transition_claim("source-a", "a-1", WorkerState.ELIGIBLE, now)
