"""Runtime Fabric V2 - portable zero-cost execution capacity, holding no authority.

The fabric answers exactly one question: **where can this capability run right
now, for free, at the revision we mean?** It never answers what to do, which
model to use, or whether a request is allowed. Those belong to GITHUB_BRAIN_V4,
`task_router` and the Model Mesh, and this module is deliberately incapable of
taking them: the authority flags are class attributes fixed at False, and
passing one to the constructor raises `TypeError` rather than being ignored.

Three rules earned the shape of this file, each from a bug in this repository:

1. **One name, one fact.** `production_eligible` is DERIVED and never stored. A
   stored eligibility flag and the facts it summarises are two things wearing
   one name, and every time that has happened here a bypass followed.

2. **A refusal must say which refusal.** `eligibility()` returns every failing
   reason, not a bare False. "Not eligible" that could mean six different things
   sends an operator to fix the wrong one - which cost a real credential
   rotation earlier in this work.

3. **Absent is not verified.** A provider having a free plan is not evidence its
   free tier was verified, and an adapter existing is not evidence it was
   deployed. Unknown is false here, never optimistic.
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).resolve().parent / "registry.yaml"

#: Every runtime state, with what it means. The tuple below is derived from
#: this table so the two can never disagree about which states exist.
RUNTIME_STATES = {
    "UNVERIFIED": "No probe has been run. Not eligible.",
    "PROBING": "A probe is in flight. Not yet eligible.",
    "HEALTHY": "Probed and serving. Eligible if every other axis passes.",
    "DEGRADED": "Answering, but failing some executions. Not eligible.",
    "RATE_LIMITED": "Provider is throttling. Not eligible until it clears.",
    "QUOTA_LOW": "Free quota nearly spent. Still eligible, but deprioritised.",
    "QUOTA_EXHAUSTED": "Free quota spent. Not eligible - and never a paid path.",
    "CIRCUIT_OPEN": "Too many failures. Excluded until cooldown elapses.",
    "HALF_OPEN": "Cooldown elapsed; one probe decides HEALTHY or CIRCUIT_OPEN.",
    "COOLDOWN": "Waiting out a circuit-open period.",
    "DISABLED": "Switched off by policy. Not eligible.",
    "QUARANTINED": "Failed promotion or violated a contract. Not eligible.",
}
STATE_VALUES = tuple(RUNTIME_STATES)

#: States a runtime may be selected in. QUOTA_LOW is present deliberately:
#: nearly-spent free quota is still free, and refusing it would push work toward
#: nothing rather than toward a cheaper path.
SELECTABLE_STATES = ("HEALTHY", "QUOTA_LOW")

#: Lifecycle, development -> stable. Only STABLE may take stable traffic.
LIFECYCLE = (
    "DISCOVERED",
    "ADAPTER_READY",
    "TESTED",
    "LIVE_PROBED",
    "VERIFIED",
    "PROMOTABLE",
    "STABLE",
)
STABLE_LIFECYCLE = "STABLE"
QUARANTINED_LIFECYCLE = "QUARANTINED"

#: The verification axes, recorded separately and never collapsed.
VERIFICATION_AXES = (
    "configured",
    "deployed",
    "health_verified",
    "exact_sha_verified",
    "free_tier_verified",
)

#: Fields an evidence record may carry. Operational facts only - never hidden
#: reasoning, never credentials. Anything not named here is refused rather than
#: silently dropped, so a caller cannot smuggle a secret through by mistake.
EVIDENCE_FIELDS = (
    "request_id",
    "trace_id",
    "source_sha",
    "runtime_id",
    "runtime_revision",
    "capability",
    "health_state_at_selection",
    "quota_state",
    "latency_ms",
    "verifier_result",
    "fallback_used",
)

NO_ELIGIBLE_RUNTIME = "CAPABILITY_TEMPORARILY_UNAVAILABLE"

#: Providers retired from the production dependency graph. A retired provider
#: returning is not a hypothetical: config is the cheapest way back in, so the
#: refusal lives here rather than in a comment. Matched against the runtime id
#: and any endpoint it declares.
RETIRED_PROVIDERS = ("railway",)


def retired_provider_reasons(runtime_id: str, entry: dict) -> list[str]:
    """Why this runtime is a retired provider trying to re-enter, if it is."""
    reasons = []
    haystacks = [str(runtime_id).lower()]
    for key in ("base_url", "endpoint", "manifest", "worker"):
        if entry.get(key):
            haystacks.append(str(entry[key]).lower())
    for provider in RETIRED_PROVIDERS:
        if any(provider in text for text in haystacks):
            reasons.append("retired_provider:%s" % provider)
    return reasons


class AuthorityViolation(TypeError):
    """Raised when something tries to give the fabric an authority it must not hold."""


def load_registry(path: Path | str | None = None) -> dict:
    return yaml.safe_load(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))


def eligibility(entry: dict, *, capability: str | None = None,
                state: str = "HEALTHY") -> tuple[bool, list[str]]:
    """Whether this runtime may serve production, and every reason it may not.

    Returns all failing reasons rather than the first: an operator fixing one
    blocker should be able to see the other five in the same breath instead of
    discovering them one deploy at a time.
    """
    reasons: list[str] = []
    verification = entry.get("verification") or {}

    for axis in VERIFICATION_AXES:
        if verification.get(axis) is not True:
            reasons.append("not_%s" % axis)

    lifecycle = entry.get("lifecycle")
    if lifecycle == QUARANTINED_LIFECYCLE:
        reasons.append("quarantined")
    elif lifecycle != STABLE_LIFECYCLE:
        reasons.append("lifecycle_not_stable:%s" % lifecycle)

    if state not in SELECTABLE_STATES:
        reasons.append("state_not_selectable:%s" % state)

    if capability is not None:
        if capability not in (entry.get("capabilities") or []):
            reasons.append("capability_unsupported:%s" % capability)
        # An ephemeral runner cannot hold an endpoint, however healthy it is.
        if capability == "http_api" and entry.get("http") is not True:
            reasons.append("not_an_http_runtime")

    return (not reasons), reasons


def production_eligible(entry: dict, **kwargs) -> bool:
    """Derived, never stored. See the module docstring."""
    return eligibility(entry, **kwargs)[0]


def zero_cost_guard(entry: dict, *, quota_state: str = "HEALTHY",
                    billing_required: bool = False) -> tuple[bool, list[str]]:
    """Refuse anything that would cost money, for any reason.

    Separate from `eligibility` on purpose: "this runtime is not ready" and
    "this runtime would charge you" are different failures needing different
    responses, and the second must never be resolved by waiting.
    """
    reasons: list[str] = []
    if billing_required:
        reasons.append("billing_required")
    if (entry.get("verification") or {}).get("free_tier_verified") is not True:
        reasons.append("free_tier_unverified")
    if quota_state == "QUOTA_EXHAUSTED":
        reasons.append("free_quota_exhausted")
    return (not reasons), reasons


class CircuitBreaker:
    """Bounded failure policy, so one transient error never causes a failover.

    Runtime ping-pong is worse than a slow runtime: it multiplies load across
    providers, burns free quota on retries, and makes evidence unreadable.
    """

    def __init__(self, *, failure_threshold: int = 3, cooldown_seconds: float = 60.0,
                 clock=time.monotonic) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._failures = 0
        self._state = "HEALTHY"
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._state == "CIRCUIT_OPEN" and self._opened_at is not None:
            if self._clock() - self._opened_at >= self.cooldown_seconds:
                return "HALF_OPEN"
        return self._state

    def record_failure(self) -> str:
        if self.state == "HALF_OPEN":
            # A failed probe re-opens immediately; it does not get another
            # threshold's worth of chances.
            self._state = "CIRCUIT_OPEN"
            self._opened_at = self._clock()
            return self._state
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "CIRCUIT_OPEN"
            self._opened_at = self._clock()
        else:
            self._state = "DEGRADED"
        return self._state

    def record_success(self) -> str:
        self._failures = 0
        self._state = "HEALTHY"
        self._opened_at = None
        return self._state


def select_runtime(registry: dict, *, capability: str,
                   states: dict[str, str] | None = None,
                   quota: dict[str, str] | None = None,
                   billing_required: dict[str, bool] | None = None
                   ) -> tuple[str | None, dict]:
    """The first eligible runtime in tier order, and why the others were not.

    Selection is by tier and evidence, never by provider brand. When nothing
    qualifies the answer is a refusal with reasons, not a best-effort guess.
    """
    states = states or {}
    quota = quota or {}
    billing_required = billing_required or {}
    runtimes = registry.get("runtimes") or {}
    rejected: dict[str, list[str]] = {}

    for tier in registry.get("tier_order") or []:
        for runtime_id, entry in sorted(runtimes.items()):
            if entry.get("tier") != tier:
                continue
            state = states.get(runtime_id, "HEALTHY")
            ok, reasons = eligibility(entry, capability=capability, state=state)
            if registry.get("railway_fallback_allowed") is not True:
                retired = retired_provider_reasons(runtime_id, entry)
                if retired:
                    rejected[runtime_id] = reasons + retired
                    continue
            free, free_reasons = zero_cost_guard(
                entry,
                quota_state=quota.get(runtime_id, "HEALTHY"),
                billing_required=billing_required.get(runtime_id, False),
            )
            if ok and free:
                return runtime_id, {"tier": tier, "state": state,
                                    "rejected": rejected}
            rejected[runtime_id] = reasons + free_reasons

    return None, {"refusal": NO_ELIGIBLE_RUNTIME, "rejected": rejected}


def build_evidence(**fields) -> dict:
    """An evidence record carrying operational facts only.

    Unknown fields are refused rather than dropped: silently discarding a field
    a caller believed was recorded is how a secret ends up believed-redacted and
    actually absent from the audit trail it was supposed to be in.
    """
    unknown = sorted(set(fields) - set(EVIDENCE_FIELDS))
    if unknown:
        raise ValueError(
            "evidence may only carry operational fields; refused: %s"
            % ", ".join(unknown))
    return dict(fields)


class RuntimeFabric:
    """One view over every runtime, holding none of the six authorities."""

    routing_authority = False
    reasoning_authority = False
    model_selection_authority = False
    admission_authority = False
    memory_authority = False
    evidence_authority = False

    _AUTHORITIES = (
        "routing_authority",
        "reasoning_authority",
        "model_selection_authority",
        "admission_authority",
        "memory_authority",
        "evidence_authority",
    )

    def __init__(self, registry: dict | None = None, **kwargs) -> None:
        offered = sorted(set(kwargs) & set(self._AUTHORITIES))
        if offered:
            raise AuthorityViolation(
                "the Runtime Fabric is capacity, not authority; refused: %s"
                % ", ".join(offered))
        unexpected = sorted(set(kwargs) - set(self._AUTHORITIES))
        if unexpected:
            raise TypeError("unexpected arguments: %s" % ", ".join(unexpected))
        self.registry = registry if registry is not None else load_registry()

    def select(self, **kwargs) -> tuple[str | None, dict]:
        return select_runtime(self.registry, **kwargs)

    def stable_runtimes(self) -> list[str]:
        return sorted(
            rid for rid, entry in (self.registry.get("runtimes") or {}).items()
            if entry.get("lifecycle") == STABLE_LIFECYCLE)

    def authority_report(self) -> dict:
        return {name: getattr(self, name) for name in self._AUTHORITIES}
