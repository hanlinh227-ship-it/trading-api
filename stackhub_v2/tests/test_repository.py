from datetime import datetime, timezone
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
