from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .payouts import ensure_payout_schema


@dataclass(frozen=True)
class RevenueSnapshot:
    paid_today_usd: Decimal
    paid_7d_usd: Decimal
    paid_30d_usd: Decimal
    by_source_usd: dict[str, Decimal]
    source_concentration: Decimal
    payout_count: int


def revenue_snapshot(repo, now: datetime | None = None) -> RevenueSnapshot:
    ensure_payout_schema(repo)
    now = now or datetime.now(timezone.utc)
    rows = repo.conn.execute(
        "SELECT source,amount_usd,paid_at FROM payout_evidence WHERE amount_usd IS NOT NULL"
    ).fetchall()

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days = now - timedelta(days=7)
    thirty_days = now - timedelta(days=30)
    paid_today = Decimal("0")
    paid_7d = Decimal("0")
    paid_30d = Decimal("0")
    by_source: dict[str, Decimal] = {}

    for row in rows:
        amount = Decimal(str(row["amount_usd"]))
        paid_at = datetime.fromisoformat(str(row["paid_at"]))
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=timezone.utc)
        source = str(row["source"])
        by_source[source] = by_source.get(source, Decimal("0")) + amount
        if paid_at >= today:
            paid_today += amount
        if paid_at >= seven_days:
            paid_7d += amount
        if paid_at >= thirty_days:
            paid_30d += amount

    total = sum(by_source.values(), Decimal("0"))
    concentration = (
        Decimal("0")
        if total == 0
        else max(by_source.values(), default=Decimal("0")) / total
    )
    return RevenueSnapshot(
        paid_today,
        paid_7d,
        paid_30d,
        by_source,
        concentration.quantize(Decimal("0.0001")),
        len(rows),
    )
