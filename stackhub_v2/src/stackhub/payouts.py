from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .source_capabilities import SourceCapabilities, assert_source_eligible_for
from .worker_state import WorkerState


@dataclass(frozen=True)
class PayoutEvidence:
    source: str
    opportunity_id: str
    payout_reference: str
    asset: str
    amount: Decimal
    amount_usd: Decimal | None
    paid_at: datetime
    raw_evidence: dict[str, object]


class PayoutSourceAdapter(Protocol):
    source_name: str
    capabilities: SourceCapabilities

    async def observe_payouts(self) -> list[PayoutEvidence]: ...


def ensure_payout_schema(repo) -> None:
    repo.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payout_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            opportunity_id TEXT NOT NULL,
            payout_reference TEXT NOT NULL,
            asset TEXT NOT NULL,
            amount TEXT NOT NULL,
            amount_usd TEXT,
            paid_at TEXT NOT NULL,
            raw_evidence_json TEXT NOT NULL,
            UNIQUE(source, payout_reference)
        )
        """
    )
    repo.conn.commit()


def record_payout(repo, evidence: PayoutEvidence) -> bool:
    ensure_payout_schema(repo)
    cursor = repo.conn.execute(
        """
        INSERT OR IGNORE INTO payout_evidence(
            source,opportunity_id,payout_reference,asset,amount,amount_usd,
            paid_at,raw_evidence_json
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            evidence.source,
            evidence.opportunity_id,
            evidence.payout_reference,
            evidence.asset,
            str(evidence.amount),
            None if evidence.amount_usd is None else str(evidence.amount_usd),
            evidence.paid_at.isoformat(),
            json.dumps(evidence.raw_evidence, default=str, sort_keys=True),
        ),
    )
    repo.conn.commit()
    inserted = cursor.rowcount > 0
    if inserted:
        row = repo.conn.execute(
            "SELECT state FROM claims WHERE source=? AND opportunity_id=?",
            (evidence.source, evidence.opportunity_id),
        ).fetchone()
        if row is not None and str(row["state"]) == WorkerState.SUBMITTED.value:
            repo.transition_claim(
                evidence.source,
                evidence.opportunity_id,
                WorkerState.PAID,
                evidence.paid_at,
            )
    return inserted


class PayoutReconciler:
    def __init__(self, repo):
        self.repo = repo

    async def reconcile(self, adapter: PayoutSourceAdapter) -> int:
        assert_source_eligible_for("observe_payout", adapter.capabilities)
        count = 0
        for evidence in await adapter.observe_payouts():
            if record_payout(self.repo, evidence):
                count += 1
        return count
