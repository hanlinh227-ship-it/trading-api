from datetime import datetime, timezone
from decimal import Decimal
import sqlite3

import pytest

from stackhub.payouts import PayoutEvidence, PayoutReconciler, record_payout
from stackhub.revenue_metrics import revenue_snapshot
from stackhub.source_capabilities import SourceCapabilities

NOW = datetime.now(timezone.utc)


class Repo:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE claims(source TEXT, opportunity_id TEXT, state TEXT)"
        )
        self.conn.execute("INSERT INTO claims VALUES('x','1','SUBMITTED')")
        self.conn.commit()
        self.transitions = []

    def transition_claim(self, source, opportunity_id, target, when):
        self.conn.execute(
            "UPDATE claims SET state=? WHERE source=? AND opportunity_id=?",
            (target.value, source, opportunity_id),
        )
        self.conn.commit()
        self.transitions.append(target.value)


class Adapter:
    source_name = "x"
    capabilities = SourceCapabilities(
        agent_allowed=True,
        auto_payout_observation=True,
        terms_verified_at=NOW,
    )

    async def observe_payouts(self):
        return [
            PayoutEvidence(
                "x",
                "1",
                "pay-1",
                "USD",
                Decimal("25"),
                Decimal("25"),
                NOW,
                {"status": "paid"},
            )
        ]


def test_submitted_reward_not_revenue_until_payout_evidence():
    repo = Repo()
    assert revenue_snapshot(repo, NOW).paid_30d_usd == 0

    record_payout(
        repo,
        PayoutEvidence(
            "x",
            "1",
            "pay-1",
            "USD",
            Decimal("25"),
            Decimal("25"),
            NOW,
            {"status": "paid"},
        ),
    )

    snapshot = revenue_snapshot(repo, NOW)
    assert snapshot.paid_today_usd == Decimal("25")
    assert repo.transitions == ["PAID"]


def test_payout_record_is_idempotent():
    repo = Repo()
    evidence = PayoutEvidence(
        "x",
        "1",
        "pay-1",
        "USD",
        Decimal("25"),
        Decimal("25"),
        NOW,
        {"status": "paid"},
    )

    assert record_payout(repo, evidence) is True
    assert record_payout(repo, evidence) is False
    assert revenue_snapshot(repo, NOW).payout_count == 1


@pytest.mark.asyncio
async def test_reconciler_uses_capability_gate():
    repo = Repo()
    assert await PayoutReconciler(repo).reconcile(Adapter()) == 1
