from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class AccountMode(StrEnum):
    AUTO = "AUTO"
    OBSERVE = "OBSERVE"
    ASSISTED = "ASSISTED"
    PAYOUT_ONLY = "PAYOUT_ONLY"


@dataclass(frozen=True)
class AccountSpec:
    name: str
    mode: AccountMode
    secret_envs: tuple[str, ...] = ()
    note: str = ""


ACCOUNT_SPECS: tuple[AccountSpec, ...] = (
    AccountSpec(
        "moltjobs",
        AccountMode.AUTO,
        ("MOLTJOBS_API_KEY",),
        "agent-native job discovery now; bidding/start/submission remain gated until mutation lifecycle verification",
    ),
    AccountSpec(
        "taskforce",
        AccountMode.AUTO,
        ("TASKFORCE_API_KEY",),
        "agent-native task discovery now; apply/accept/submit remain gated until application lifecycle verification",
    ),
    AccountSpec(
        "taskbounty",
        AccountMode.AUTO,
        ("TASKBOUNTY_API_KEY",),
        "job discovery/claim/submit after live capability verification",
    ),
    AccountSpec(
        "gumroad",
        AccountMode.OBSERVE,
        ("GUMROAD_ACCESS_TOKEN",),
        "API observation/management only; product creation/upload remains assisted",
    ),
    AccountSpec(
        "rapidapi",
        AccountMode.ASSISTED,
        (),
        "provider account and payout stay platform-managed; API automation requires explicit Platform API entitlement",
    ),
    AccountSpec(
        "adobe_stock",
        AccountMode.ASSISTED,
        (),
        "Contributor Portal upload/review gate; no account password is stored",
    ),
    AccountSpec(
        "paypal",
        AccountMode.PAYOUT_ONLY,
        (),
        "payout rail only; STACKHUB never requests PayPal credentials",
    ),
    AccountSpec(
        "github",
        AccountMode.ASSISTED,
        (),
        "repository authorization is handled by the deployment/tooling layer, not marketplace secrets",
    ),
)


def account_status(env: Mapping[str, str]) -> tuple[dict[str, object], ...]:
    """Return integration readiness without ever returning secret values."""
    rows: list[dict[str, object]] = []
    for spec in ACCOUNT_SPECS:
        missing = tuple(
            env_name
            for env_name in spec.secret_envs
            if not str(env.get(env_name, "")).strip()
        )
        rows.append(
            {
                "name": spec.name,
                "mode": spec.mode.value,
                "ready_for_mode": not missing,
                "missing_secrets": missing,
                "note": spec.note,
            }
        )
    return tuple(rows)
