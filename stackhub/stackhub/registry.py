from __future__ import annotations

from .models import AutomationClass, SourcePolicy


_SOURCES: tuple[SourcePolicy, ...] = (
    SourcePolicy(
        slug="grass",
        name="Grass",
        automation_class=AutomationClass.PASSIVE_ALLOWED,
        payout_assets=("USDC",),
        notes="Background earning source; monitoring only until a documented automation interface is verified.",
    ),
    SourcePolicy(
        slug="honeygain",
        name="Honeygain",
        automation_class=AutomationClass.PASSIVE_ALLOWED,
        payout_assets=("JMPT",),
        notes="Only on user-owned/authorized devices and connections; no artificial traffic generation.",
    ),
    SourcePolicy(
        slug="pawns",
        name="Pawns.app",
        automation_class=AutomationClass.PASSIVE_ALLOWED,
        payout_assets=("BTC",),
        residential_only=True,
        notes="Passive sharing requires residential networking; block on VPS/server environments.",
    ),
    SourcePolicy(
        slug="jumptask",
        name="JumpTask",
        automation_class=AutomationClass.DISCOVERY_ONLY,
        payout_assets=("JMPT", "USDC", "BTC", "ETH", "TRX"),
        notes="STACKHUB may discover/rank tasks; execution remains human-required unless official automation is explicitly permitted.",
    ),
)


def get_sources() -> tuple[SourcePolicy, ...]:
    return _SOURCES
