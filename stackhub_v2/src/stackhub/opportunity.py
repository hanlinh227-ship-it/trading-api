from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .models import Opportunity as LegacyOpportunity


class RevenueLane(StrEnum):
    EXTERNAL_JOB = "external_job"
    SERVICE_API = "service_api"
    DIGITAL_ASSET = "digital_asset"


class NormalizedOpportunity(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    lane: RevenueLane = RevenueLane.EXTERNAL_JOB
    task_class: str = Field(min_length=1)
    reward_amount: Decimal = Field(ge=Decimal("0"))
    reward_asset: str = Field(min_length=1)
    reward_network: str | None = None
    reward_usd_estimate: Decimal | None = Field(default=None, ge=Decimal("0"))
    deadline: datetime | None = None
    requirements: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    agent_allowed: bool | None = None
    estimated_effort_minutes: int = Field(default=60, ge=1)
    metadata: dict[str, object] = {}

    @property
    def id(self) -> str:
        return self.external_id


def normalize_legacy(
    opportunity: LegacyOpportunity,
    *,
    title: str | None = None,
    lane: RevenueLane = RevenueLane.EXTERNAL_JOB,
) -> NormalizedOpportunity:
    return NormalizedOpportunity(
        source=opportunity.source,
        external_id=opportunity.id,
        title=title or f"{opportunity.category}:{opportunity.id}",
        url=opportunity.url,
        lane=lane,
        task_class=opportunity.category,
        reward_amount=opportunity.reward.amount,
        reward_asset=opportunity.reward.asset,
        reward_network=opportunity.reward.network,
        reward_usd_estimate=(
            opportunity.reward.amount if opportunity.reward.asset.upper() == "USD" else None
        ),
        deadline=opportunity.deadline,
        requirements=opportunity.requirements,
        acceptance_criteria=opportunity.acceptance_criteria,
        agent_allowed=opportunity.agent_allowed,
        estimated_effort_minutes=opportunity.estimated_effort_minutes or 60,
    )
