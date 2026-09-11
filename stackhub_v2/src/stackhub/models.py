from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Reward(BaseModel):
    model_config = ConfigDict(frozen=True)
    amount: Decimal = Field(ge=Decimal("0"))
    asset: str = Field(min_length=1)
    network: str | None = None


class Opportunity(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    url: str = Field(min_length=1)
    category: Literal["coding", "research", "data", "content", "automation", "other"]
    reward: Reward
    deadline: datetime | None = None
    requirements: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    competition_model: str = "other"
    agent_allowed: bool | None = None
    estimated_effort_minutes: int | None = Field(default=None, ge=1)
