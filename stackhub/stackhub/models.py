from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AutomationClass(str, Enum):
    PASSIVE_ALLOWED = "PASSIVE_ALLOWED"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    name: str
    automation_class: AutomationClass
    payout_assets: tuple[str, ...]
    slug: str = ""
    residential_only: bool = False
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Opportunity:
    source: str
    title: str
    expected_reward_usd: float
    estimated_minutes: float
    approval_probability: float = 1.0
    requires_deposit: bool = False
    payout_threshold_usd: float = 0.0
    current_balance_usd: float = 0.0
