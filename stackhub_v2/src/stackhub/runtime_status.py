from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from .revenue_metrics import revenue_snapshot


@dataclass(frozen=True)
class RuntimeStatus:
    opportunities: int
    active_claims: int
    awaiting_submission: int
    payout_pending: int
    paid_today_usd: Decimal
    paid_7d_usd: Decimal
    paid_30d_usd: Decimal
    source_concentration: Decimal
    source_health: dict[str, dict[str, object]]


def build_status(repo) -> RuntimeStatus:
    def count(sql: str, params=()) -> int:
        return int(repo.conn.execute(sql, params).fetchone()[0])

    opportunities = count("SELECT COUNT(*) FROM opportunities")
    active_claims = count(
        "SELECT COUNT(*) FROM claims WHERE state NOT IN ('PAID','FAILED_PERMANENT','EXPIRED','REJECTED')"
    )
    awaiting_submission = count(
        "SELECT COUNT(*) FROM claims WHERE state='VERIFIED'"
    )
    payout_pending = count(
        "SELECT COUNT(*) FROM claims WHERE state='SUBMITTED'"
    )
    rows = repo.conn.execute(
        """
        SELECT h.*
        FROM source_health h
        JOIN (
            SELECT source, MAX(id) AS id
            FROM source_health
            GROUP BY source
        ) latest ON h.id=latest.id
        """
    ).fetchall()
    source_health = {
        str(row["source"]): {
            "ok": bool(row["ok"]),
            "status_code": row["status_code"],
            "error_code": row["error_code"],
            "observed_at": row["observed_at"],
        }
        for row in rows
    }
    revenue = revenue_snapshot(repo)
    return RuntimeStatus(
        opportunities,
        active_claims,
        awaiting_submission,
        payout_pending,
        revenue.paid_today_usd,
        revenue.paid_7d_usd,
        revenue.paid_30d_usd,
        revenue.source_concentration,
        source_health,
    )


def status_dict(status: RuntimeStatus) -> dict[str, object]:
    return asdict(status)
