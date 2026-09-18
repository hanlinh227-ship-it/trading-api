from __future__ import annotations

from dataclasses import dataclass
import re

from .config import RuntimeConfig
from .models import Opportunity


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]


_HUMAN_SIMULATION_PATTERNS = (
    r"\bcaptcha\b", r"\bact as a human\b", r"\bhuman reviewer\b",
    r"\bfake (click|view|engagement|survey|gameplay)\b", r"\bimpersonat(e|ion)\b", r"\bspoof (ip|location|device)\b",
)
_WALLET_SECRET_PATTERNS = (r"\bseed phrase\b", r"\bmnemonic\b", r"\bprivate key\b")
_PROMPT_INJECTION_PATTERNS = (r"ignore previous (instructions|policy)", r"override (system|policy)", r"enable spending", r"disable (guardrail|policy|safety)")
_TRADING_TARGET_PATTERNS = (r"production trading", r"live trading", r"bybit production", r"mt5 production")
_EXTERNAL_ACCOUNT_PATTERNS = (
    r"\bpost (an?|the|this)?\s*(instagram|tiktok|facebook|linkedin|youtube|x|twitter)\b",
    r"\bpublish (an?|the|this)?\s*(instagram|tiktok|facebook|linkedin|youtube|x|twitter)\b",
    r"\bfrom your (account|profile|channel)\b", r"\bsend the public link\b", r"\buse your personal account\b",
    r"\bnative[_ -]?forum[_ -]?proof\b", r"\boriginal visible contribution\b.*\bverified authorship\b",
)
_PERSONAL_PHYSICAL_PATTERNS = (
    r"\brecord (a |your )?face\b", r"\bface motion video\b", r"\bfront camera\b.*\b(face|head)\b",
    r"\bfull face\b", r"\bone submission per person\b", r"\bsign a consent form\b",
)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = " ".join(text.lower().split())
    return any(re.search(pattern, normalized) for pattern in patterns)


def evaluate_opportunity(opportunity: Opportunity, runtime: RuntimeConfig) -> PolicyDecision:
    reasons: list[str] = []
    opportunity_allowlist = tuple(getattr(runtime, "opportunity_allowlist", ()) or ())
    if opportunity_allowlist and opportunity.id not in opportunity_allowlist:
        reasons.append("not_in_runtime_opportunity_allowlist")
    if opportunity.agent_allowed is not True:
        reasons.append("agent_permission_unknown" if opportunity.agent_allowed is None else "agent_permission_forbidden")
    source = runtime.sources.get(opportunity.source)
    worker_enabled = bool(getattr(runtime, "worker_enabled", False))
    if source is None or not source.enabled or not source.agent_native:
        reasons.append("source_not_enabled_for_agents")
    elif worker_enabled and (source.read_only or not source.capabilities.auto_claim):
        # Keep discovery-only sources visible in scans/status, but never reserve them for a live worker.
        reasons.append("source_not_mutation_ready")

    combined_text = "\n".join((*opportunity.requirements, *opportunity.acceptance_criteria))
    if _matches_any(combined_text, _HUMAN_SIMULATION_PATTERNS): reasons.append("prohibited_human_simulation")
    if _matches_any(combined_text, _WALLET_SECRET_PATTERNS): reasons.append("prohibited_wallet_secret")
    if _matches_any(combined_text, _PROMPT_INJECTION_PATTERNS): reasons.append("prompt_injection_like_instruction")
    if _matches_any(combined_text, _TRADING_TARGET_PATTERNS): reasons.append("prohibited_production_trading_target")
    if _matches_any(combined_text, _EXTERNAL_ACCOUNT_PATTERNS): reasons.append("prohibited_external_account_action")
    if _matches_any(combined_text, _PERSONAL_PHYSICAL_PATTERNS): reasons.append("prohibited_personal_physical_task")

    spend_terms = ("deposit", "purchase", "pay fee", "buy credits", "external spend")
    normalized = combined_text.lower()
    if runtime.external_spend_limit_usd == 0 and any(term in normalized for term in spend_terms):
        reasons.append("external_spend_required")

    deduped = tuple(dict.fromkeys(reasons))
    return PolicyDecision(allowed=not deduped, reasons=deduped)
