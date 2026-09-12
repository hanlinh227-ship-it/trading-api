from datetime import datetime, timedelta, timezone
from decimal import Decimal
from stackhub.models import Opportunity, Reward
from stackhub.policy import PolicyDecision
from stackhub.scoring import ScoreResult
from stackhub.repository import StackHubRepository


def opp(amount="20"):
    return Opportunity(
        id="tb-1", source="taskbounty", url="https://www.task-bounty.com/task/tb-1", category="coding",
        reward=Reward(amount=Decimal(amount), asset="USD", network=None), deadline=None,
        requirements=("Fix bug",), acceptance_criteria=("Tests pass",), competition_model="best_submission",
        agent_allowed=True, estimated_effort_minutes=20,
    )


def test_duplicate_upsert_is_idempotent(tmp_path):
    repo = StackHubRepository(tmp_path / "stackhub.db")
    repo.initialize()
    p = PolicyDecision(True, ())
    s = ScoreResult(expected_net_value_usd=Decimal("8.00"), score_usd_per_minute=Decimal("0.4000"))
    repo.upsert_opportunity(opp(), p, s)
    repo.upsert_opportunity(opp(), p, s)
    rows = repo.list_ranked_opportunities()
    assert len(rows) == 1
    assert rows[0]["id"] == "tb-1"


def test_reopen_and_update_reward_keeps_one_row(tmp_path):
    path = tmp_path / "stackhub.db"
    p = PolicyDecision(True, ())
    s = ScoreResult(expected_net_value_usd=Decimal("8.00"), score_usd_per_minute=Decimal("0.4000"))
    r1 = StackHubRepository(path); r1.initialize(); r1.upsert_opportunity(opp("20"), p, s); r1.close()
    r2 = StackHubRepository(path); r2.initialize(); r2.upsert_opportunity(opp("30"), p, s)
    rows = r2.list_ranked_opportunities()
    assert len(rows) == 1
    assert rows[0]["reward_amount"] == "30"


def test_source_health_keeps_history_and_latest(tmp_path):
    repo = StackHubRepository(tmp_path / "stackhub.db"); repo.initialize()
    t1 = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 11, 10, 5, tzinfo=timezone.utc)
    repo.record_source_health("taskbounty", False, 503, "upstream_503", t1)
    repo.record_source_health("taskbounty", True, 200, None, t2)
    latest = repo.get_source_health("taskbounty")
    assert latest["ok"] is True
    assert repo.count_source_health("taskbounty") == 2


def test_initialize_quarantines_closed_taskforce_availability_failure(tmp_path):
    path = tmp_path / "stackhub.db"
    repo = StackHubRepository(path)
    repo.initialize()
    repo.conn.execute(
        "INSERT INTO claims(source,opportunity_id,state,updated_at,last_error_code) VALUES(?,?,?,?,?)",
        (
            "taskforce",
            "tf-closed",
            "FAILED_RETRYABLE",
            "2026-09-11T20:00:00+00:00",
            "task_not_accepting_applications:http_400",
        ),
    )
    repo.conn.commit()
    repo.close()

    reopened = StackHubRepository(path)
    reopened.initialize()
    claim = reopened.get_claim("taskforce", "tf-closed")

    assert claim["state"] == "FAILED_PERMANENT"
    assert claim["last_error_code"] == "task_not_accepting_applications:http_400"


def test_initialize_keeps_closed_taskforce_permanent_failure_terminal(tmp_path):
    path = tmp_path / "stackhub.db"
    repo = StackHubRepository(path)
    repo.initialize()
    repo.conn.execute(
        "INSERT INTO claims(source,opportunity_id,state,updated_at,last_error_code) VALUES(?,?,?,?,?)",
        (
            "taskforce",
            "tf-closed-terminal",
            "FAILED_PERMANENT",
            "2026-09-11T20:00:00+00:00",
            "task_not_accepting_applications:http_400",
        ),
    )
    repo.conn.commit()
    repo.close()

    reopened = StackHubRepository(path)
    reopened.initialize()
    claim = reopened.get_claim("taskforce", "tf-closed-terminal")

    assert claim["state"] == "FAILED_PERMANENT"


def test_initialize_rearms_legacy_generic_taskforce_http400_failure_once_for_reclassification(tmp_path):
    path = tmp_path / "stackhub.db"
    repo = StackHubRepository(path)
    repo.initialize()
    repo.conn.execute(
        "INSERT INTO claims(source,opportunity_id,state,updated_at,last_error_code) VALUES(?,?,?,?,?)",
        (
            "taskforce",
            "tf-legacy-400",
            "FAILED_PERMANENT",
            "2026-09-11T20:00:00+00:00",
            "http_400:http_400",
        ),
    )
    repo.conn.commit()
    repo.close()

    reopened = StackHubRepository(path)
    reopened.initialize()
    claim = reopened.get_claim("taskforce", "tf-legacy-400")

    assert claim["state"] == "FAILED_RETRYABLE"
    assert claim["last_error_code"] == "http_400:http_400"


def test_failed_retryable_claim_waits_for_retry_cooldown(tmp_path):
    repo = StackHubRepository(tmp_path / "stackhub.db")
    repo.initialize()
    p = PolicyDecision(True, ())
    s = ScoreResult(expected_net_value_usd=Decimal("8.00"), score_usd_per_minute=Decimal("0.4000"))
    repo.upsert_opportunity(opp(), p, s)
    failed_at = datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc)
    repo.conn.execute(
        "INSERT INTO claims(source,opportunity_id,state,updated_at,last_error_code) VALUES(?,?,?,?,?)",
        (
            "taskbounty",
            "tb-1",
            "FAILED_RETRYABLE",
            failed_at.isoformat(),
            "protocol_error",
        ),
    )
    repo.conn.commit()

    assert repo.reserve_next_opportunity(None, 4, failed_at + timedelta(minutes=1)) is None
    reserved = repo.reserve_next_opportunity(None, 4, failed_at + timedelta(minutes=6))
    assert reserved is not None
    assert reserved["id"] == "tb-1"
