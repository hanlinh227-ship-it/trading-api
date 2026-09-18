from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Action = Literal["discover", "claim", "submit", "publish", "observe_payout"]


class SourceCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_class: str = "job"
    agent_allowed: bool = False
    auto_discovery: bool = False
    auto_claim: bool = False
    auto_execute: bool = False
    auto_submit: bool = False
    auto_publish: bool = False
    auto_payout_observation: bool = False
    requires_human_onboarding: bool = True
    requires_kyc: bool = False
    requires_tax_setup: bool = False
    requires_manual_review: bool = False
    external_spend_required: bool = False
    mutation_verified_at: datetime | None = None
    terms_verified_at: datetime | None = None
    rate_limit_policy: str | None = None


def assert_source_eligible_for(action: Action, capabilities: SourceCapabilities) -> None:
    if capabilities.external_spend_required:
        raise ValueError("source requires external spend")
    if not capabilities.agent_allowed:
        raise ValueError("source is not verified agent-allowed")

    if action == "discover":
        if not capabilities.auto_discovery:
            raise ValueError("automated discovery is not enabled")
        return

    enabled = {
        "claim": capabilities.auto_claim,
        "submit": capabilities.auto_submit,
        "publish": capabilities.auto_publish,
        "observe_payout": capabilities.auto_payout_observation,
    }[action]
    if not enabled:
        raise ValueError(f"automated {action} is not enabled")
    if action in {"claim", "submit", "publish"} and capabilities.mutation_verified_at is None:
        raise ValueError(f"automated {action} requires verified mutation capability")
    if capabilities.terms_verified_at is None:
        raise ValueError(f"automated {action} requires current terms verification")
