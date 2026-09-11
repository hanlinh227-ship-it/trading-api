from __future__ import annotations

import re
from dataclasses import dataclass

from .config import RuntimeConfig
from .models import Opportunity


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]


_HUMAN_SIM = (
    re.compile(r"\bcaptcha\b", re.I),
    re.compile(r"\bact as (?:a )?human\b", re.I),
    re.compile(r"\bfake (?:clicks?|views?|engagement|survey|identity)\b", re.I),
    re.compile(r"\bspoof (?:location|ip|device)\b", re.I),
)
_WALLET_SECRET = (
    re.compile(r"\bseed phrase\b", re.I),
    re.compile(r"\bprivate key\b", re.I),
    re.compile(r"\bmnemonic\b", re.I),
)
_EXTERNAL_SPEND = (
    re.compile(r"\b(?:pay|purchase|buy|deposit|fund)\b.*\b(?:usd|usdc|usdt|eth|btc|dollars?|crypto)\b", re.I),
)
_TRADING_PROD = (
    re.compile(r"\bproduction trading\b", re.I),
    re.compile(r"\blive trading bot\b", re.I),
    re.compile(r"\bbybit production\b", re.I),
)


def _joined_text(opportunity: Opportunity) -> str:
    return "\n".join((*opportunity.requirements, *opportunity.acceptance_criteria))


def evaluate_opportunity(opportunity: Opportunity, runtime: RuntimeConfig) -> PolicyDecision:
    reasons: list[str] = []
    source = runtime.sources.get(opportunity.source)

    if opportunity.agent_allowed is None:
        reasons.append("agent_permission_unknown")
    elif opportunity.agent_allowed is False:
        reasons.append("agent_permission_forbidden")

    if source is None or not source.enabled:
        reasons.append("source_disabled_or_unknown")
    elif not source.agent_native:
        reasons.append("source_not_agent_native")

    text = _joined_text(opportunity)
    if any(pattern.search(text) for pattern in _HUMAN_SIM):
        reasons.append("prohibited_human_simulation")
    if any(pattern.search(text) for pattern in _WALLET_SECRET):
        reasons.append("prohibited_wallet_secret")
    if any(pattern.search(text) for pattern in _TRADING_PROD):
        reasons.append("prohibited_production_trading_scope")
    if runtime.external_spend_limit_usd <= 0 and any(pattern.search(text) for pattern in _EXTERNAL_SPEND):
        reasons.append("external_spend_required")

    return PolicyDecision(allowed=not reasons, reasons=tuple(dict.fromkeys(reasons)))
