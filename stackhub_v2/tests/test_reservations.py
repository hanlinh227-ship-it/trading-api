from datetime import datetime, timedelta, timezone

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


def test_failed_retryable_frees_capacity_then_retries_after_cooldown(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "source-a", "a-1", 10)
    _seed(repo, "source-b", "b-1", 1)
    now = datetime.now(timezone.utc)

    first = repo.reserve_next_opportunity(None, 1, now)
    assert first is not None
    assert first["opportunity_id"] == "a-1"
    repo.transition_claim("source-a", "a-1", WorkerState.FAILED_RETRYABLE, now, "temporary")

    replacement = repo.reserve_next_opportunity(None, 1, now)
    assert replacement is not None
    assert replacement["source"] == "source-b"
    assert replacement["opportunity_id"] == "b-1"
    failed_claim = repo.get_claim("source-a", "a-1")
    assert failed_claim is not None
    assert failed_claim["state"] == WorkerState.FAILED_RETRYABLE.value

    retry = repo.reserve_next_opportunity(None, 2, now + timedelta(minutes=6))
    assert retry is not None
    assert retry["source"] == "source-a"
    assert retry["opportunity_id"] == "a-1"
    claim = repo.get_claim("source-a", "a-1")
    assert claim is not None
    assert claim["state"] == WorkerState.RESERVED.value
    assert claim["last_error_code"] is None


def test_reservation_ignores_opportunity_not_seen_in_latest_successful_source_scan(tmp_path):
    repo = StackHubRepository(tmp_path / "reservations.db")
    repo.initialize()
    _seed(repo, "taskforce", "stale-high-score", 100)
    _seed(repo, "taskforce", "fresh-low-score", 1)

    scan_time = datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc)
    repo.conn.execute(
        "UPDATE opportunities SET updated_at=? WHERE source=? AND id=?",
        ("2026-09-11 23:59:00", "taskforce", "stale-high-score"),
    )
    repo.conn.execute(
        "UPDATE opportunities SET updated_at=? WHERE source=? AND id=?",
        ("2026-09-12 00:00:01", "taskforce", "fresh-low-score"),
    )
    repo.conn.commit()
    repo.record_source_health("taskforce", True, 200, None, scan_time)

    selected = repo.reserve_next_opportunity(None, 1, scan_time + timedelta(minutes=1))

    assert selected is not None
    assert selected["id"] == "fresh-low-score"


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
