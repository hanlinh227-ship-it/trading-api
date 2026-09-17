"""Execution paths that hold no weights of ours: hosted, serverless inference.

A worker is a machine we hand an artifact to. A **provider** is the opposite
arrangement: it holds its own weights, exposes them under its own name, and
will not take ours. Both can execute a request, so both belong in the placement
answer - but collapsing them loses the fact that decides everything downstream.

The distinction that matters is **exact model versus capability fallback.**
Cloudflare Workers AI serving `@cf/openai/gpt-oss-20b` is the same model the
registry admitted, so a benchmark taken there is a measurement of that model.
Cloudflare serving `@cf/qwen/qwen2.5-coder-32b-instruct` when the request was
for Qwen3-Coder-30B is a *different model that does a similar job*, and a
benchmark taken there measures the substitute. Recording the second as if it
were the first would put an unmeasured model's score against a measured model's
name, which is the exact failure the digest-binding rule exists to prevent - and
a provider-hosted model has no artifact digest to bind to at all.

So an offering carries a `match` that is one of:

  EXACT          the provider serves the same model the record names
  CAPABILITY     the provider serves something else that covers the capability
  ABSENT         the provider does not serve it, checked
  UNVERIFIED     not established either way, which is not the same as ABSENT

and nothing in this module ever promotes CAPABILITY to EXACT.

**What a provider cannot do is as load-bearing as what it can.** A hosted
catalog will not run an arbitrary GGUF; `custom_weights` records that, so a
model whose only blocker was local RAM does not quietly become "available"
somewhere that could never load its artifact. A provider that cannot take our
weights can still answer the capability - under its own model's name, with its
own evidence.

Providers hold no authority here either. `routing_authority` and friends are
class attributes fixed at False, exactly as on a worker: passing one is a
TypeError. This records where execution is possible. `task_router` and the
Model Mesh keep the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class ProviderError(RuntimeError):
    """A provider record that policy or the contract does not allow."""


class ExecutionType(str, Enum):
    """How the compute is obtained, which is what its constraints follow from."""

    #: Our process, our weights, our machine.
    LOCAL_PROCESS = "LOCAL_PROCESS"
    #: A per-job runner we start: real RAM and disk, but it ends.
    EPHEMERAL_JOB = "EPHEMERAL_JOB"
    #: Someone else's hosted catalog behind an API. No weights of ours ever land.
    SERVERLESS_HOSTED_CATALOG = "SERVERLESS_HOSTED_CATALOG"


class OfferingMatch(str, Enum):
    EXACT = "EXACT"
    CAPABILITY = "CAPABILITY"
    ABSENT = "ABSENT"
    UNVERIFIED = "UNVERIFIED"


class ProviderVerification(str, Enum):
    """How far a provider has got from "we read about it" to "it ran".

    The ordering is deliberate and the line is between the first four and the
    rest: **only a state that required a real execution admits a provider.** A
    catalog page, a pricing table and a published limit are all evidence about
    the world and none of them is evidence that this account can call this model
    today. A provider that has never returned a completion is DISCOVERED, and
    calling it available would be the same error as recording a documentation
    score in the capability ledger.
    """

    #: Found and recorded. Nothing has been attempted.
    DISCOVERED = "DISCOVERED"
    #: An attempt is warranted but has not been made or has not concluded.
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    #: Attempted, and the credential was missing or rejected for this API. The
    #: remedy is a token, and it belongs to a person.
    AUTH_REQUIRED = "AUTH_REQUIRED"
    #: Attempted, and it needs an account or connection only the operator can make.
    HUMAN_CONNECTION_REQUIRED = "HUMAN_CONNECTION_REQUIRED"
    #: Reachable, but out of free allowance until it resets.
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    #: Reachable and answering, but not on any zero-cost tier.
    PAID_ONLY = "PAID_ONLY"
    #: Its terms do not permit the use we would make of it. Never worked around.
    TERMS_INCOMPATIBLE = "TERMS_INCOMPATIBLE"
    #: Cannot serve what we need at all - wrong modality, wrong interface.
    UNSUPPORTED = "UNSUPPORTED"
    #: Was verified, is not answering now.
    OFFLINE = "OFFLINE"
    #: It ran. A real request returned a real completion on a zero-cost tier.
    VERIFIED_AVAILABLE = "VERIFIED_AVAILABLE"
    #: It ran, within constraints worth recording (a narrow model set, a low cap).
    VERIFIED_LIMITED = "VERIFIED_LIMITED"


#: The only two states in which a provider may actually be selected. Everything
#: else is a stage on the way, and none of them is availability.
VERIFIED_STATES = frozenset({
    ProviderVerification.VERIFIED_AVAILABLE,
    ProviderVerification.VERIFIED_LIMITED,
})

#: States that are facts about the provider itself and hold on every machine.
PERMANENT_REFUSAL_STATES = frozenset({
    ProviderVerification.PAID_ONLY,
    ProviderVerification.TERMS_INCOMPATIBLE,
    ProviderVerification.UNSUPPORTED,
})


class CostClass(str, Enum):
    #: Free and unable to bill: the plan has no billing path at all, so an
    #: overrun fails rather than charges.
    FREE_HARD_STOP = "FREE_HARD_STOP"
    #: Free within a quota, on an account that *could* be billed. Not usable
    #: autonomously without a verified hard stop.
    FREE_QUOTA_SOFT = "FREE_QUOTA_SOFT"
    #: Hardware already owned; running it costs nothing further.
    OWNED_ZERO_MARGINAL = "OWNED_ZERO_MARGINAL"
    #: Billable. Never selected autonomously.
    PAID = "PAID"


#: Cost classes a FREE_ONLY request may use without human approval. A soft
#: quota on a billable account is deliberately excluded: "free until it isn't"
#: is not free.
AUTONOMOUS_COST_CLASSES = frozenset({
    CostClass.FREE_HARD_STOP,
    CostClass.OWNED_ZERO_MARGINAL,
})


@dataclass(frozen=True)
class ModelOffering:
    """One model a provider serves, and how it relates to the one we asked for."""

    requested_model_id: str
    match: OfferingMatch
    provider_model_id: str | None = None
    #: Why this is a stand-in, when it is one. Required for CAPABILITY, because
    #: an unexplained substitution is indistinguishable from a mistake.
    substitution_reason: str | None = None
    context_window: int | None = None
    #: Free-tier reachability is a separate question from catalog presence: a
    #: model can be listed and still 403 on the free plan.
    free_tier_eligible: bool | None = None
    unit_pricing: str | None = None
    license_note: str | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.match is OfferingMatch.CAPABILITY and not self.substitution_reason:
            raise ProviderError(
                f"{self.requested_model_id}: a CAPABILITY offering must say why it is a "
                f"stand-in; an unexplained substitution reads as the real model"
            )
        if self.match in {OfferingMatch.EXACT, OfferingMatch.CAPABILITY} and not self.provider_model_id:
            raise ProviderError(
                f"{self.requested_model_id}: an offering that claims to serve something "
                f"must name what it serves"
            )

    @property
    def is_the_requested_model(self) -> bool:
        return self.match is OfferingMatch.EXACT

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "requested_model_id": self.requested_model_id,
            "match": self.match.value,
            "provider_model_id": self.provider_model_id,
            "is_the_requested_model": self.is_the_requested_model,
            "substitution_reason": self.substitution_reason,
            "context_window": self.context_window,
            "free_tier_eligible": self.free_tier_eligible,
            "unit_pricing": self.unit_pricing,
            "license_note": self.license_note,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ProviderRecord:
    """An execution path that is not a machine of ours.

    Every capability field defaults to the answer that keeps a model *off* this
    path. A provider that has not been established to support custom weights
    does not get the benefit of the doubt, because the cost of wrongly assuming
    it does is a model recorded as available on a path that cannot load it.
    """

    provider_id: str
    execution_type: ExecutionType
    cost_class: CostClass

    #: Can we give it weights? A hosted catalog cannot, and that is the single
    #: fact that decides whether a REMOTE_WORKER_REQUIRED model is solved here
    #: or merely substituted for.
    custom_weights: bool = False
    supported_artifact_formats: frozenset[str] = frozenset()

    #: Does a credential have to exist for this path to run at all, and does
    #: this container hold one? Two questions, because "needs auth" and "we are
    #: authenticated" have different remedies.
    authentication_required: bool = True
    credential_available_here: bool = False

    #: Whether the path keeps a loaded model between requests. A serverless
    #: catalog does this for us and charges nothing for it; an ephemeral job
    #: does not, which is why its cold start is the whole latency.
    model_cache_capability: str = "none"
    cold_start_ms: int | None = None

    max_job_seconds: int | None = None
    max_ram_mb: int | None = None
    max_disk_mb: int | None = None
    quota: str | None = None
    quota_resets: str | None = None
    egress_note: str | None = None
    #: How a real inference on this path could be proven, or why it cannot be
    #: proven from here. Never a claim that one *was* proven.
    inference_provable_by: str | None = None
    offerings: tuple[ModelOffering, ...] = ()
    notes: str = ""
    evidence: tuple[str, ...] = ()

    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False
    admission_authority = False

    def offering_for(self, model_id: str) -> ModelOffering | None:
        for offering in self.offerings:
            if offering.requested_model_id == model_id:
                return offering
        return None

    #: Whether the operator's own account already has this path enabled. A
    #: credential missing from *this container* and a path the federation does
    #: not have are different facts with different remedies, and the second is
    #: the only one that disqualifies a model.
    operator_authorized: bool = False
    operator_evidence: str | None = None

    #: How far this path has been verified. Defaults to DISCOVERED, so a
    #: provider added from documentation is not available until something has
    #: actually run on it.
    #: A worker that holds this provider's credential when this runtime does
    #: not. The distinction is real and was earned: the Workers AI probe ran
    #: three completions from a GitHub Actions runner while this container held
    #: no Cloudflare token at all. Treating that as "no access" would have been
    #: false - the federation reaches the provider, just not from here.
    credential_held_by_worker: str | None = None

    verification_state: ProviderVerification = ProviderVerification.DISCOVERED
    verification_evidence: str | None = None
    operator_action_required: str | None = None

    @property
    def reachable_only_by_dispatch(self) -> str | None:
        """The worker a request must go through, when this runtime cannot call it.

        Not a blocker: the provider is reachable and proven. It is a routing
        fact, and the caller needs it because the request has to be dispatched
        rather than made here.
        """
        if self.credential_available_here or not self.authentication_required:
            return None
        return self.credential_held_by_worker

    @property
    def usable_without_approval(self) -> bool:
        """Zero-cost and reachable from here. Both, or it is not usable now."""
        return (
            self.cost_class in AUTONOMOUS_COST_CLASSES
            and (self.credential_available_here or not self.authentication_required)
        )

    def federation_blockers(self) -> tuple[str, ...]:
        """Why this path is not available to the federation at all.

        Cost only. These are properties of the path itself, so they hold on
        every machine and no amount of provisioning here changes them.
        """
        why: list[str] = []
        if self.cost_class is CostClass.PAID:
            why.append("is a paid path; no paid fallback without explicit human approval")
        elif self.cost_class is CostClass.FREE_QUOTA_SOFT:
            why.append(
                "free quota sits on an account that can be billed past it, so it has no "
                "verified hard stop and is not usable autonomously"
            )
        if self.authentication_required and not self.operator_authorized:
            why.append(
                "requires an account this federation has not been shown to have; "
                "enabling one is an operator decision, not an autonomous one"
            )
        if self.verification_state in PERMANENT_REFUSAL_STATES:
            why.append(
                f"is {self.verification_state.value}, which is a fact about the provider "
                f"and does not change with the machine asking"
            )
        return tuple(why)

    def local_blockers(self) -> tuple[str, ...]:
        """Why *this container* cannot drive the path, though the path exists.

        Scoped exactly like a host RAM measurement: a statement about this
        runtime, never about the model or the provider. A model is not
        disqualified by these.
        """
        why: list[str] = []
        if (self.authentication_required and not self.credential_available_here
                and not self.credential_held_by_worker):
            why.append(
                "this runtime holds no credential for it, no worker holds one either, "
                "and one must not be written into the repository to create one"
            )
        if self.verification_state not in VERIFIED_STATES:
            # The rule that keeps a catalog page out of the availability column.
            detail = f"; {self.operator_action_required}" if self.operator_action_required else ""
            why.append(
                f"has never returned a completion on a zero-cost tier (state: "
                f"{self.verification_state.value}); documentation is not execution proof"
                f"{detail}"
            )
        return tuple(why)

    def blockers(self) -> tuple[str, ...]:
        """Everything standing in the way, both scopes, for a quick read."""
        return self.federation_blockers() + self.local_blockers()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "provider_id": self.provider_id,
            "execution_type": self.execution_type.value,
            "cost_class": self.cost_class.value,
            "custom_weights": self.custom_weights,
            "supported_artifact_formats": sorted(self.supported_artifact_formats),
            "authentication_required": self.authentication_required,
            "credential_available_here": self.credential_available_here,
            "model_cache_capability": self.model_cache_capability,
            "cold_start_ms": self.cold_start_ms,
            "max_job_seconds": self.max_job_seconds,
            "max_ram_mb": self.max_ram_mb,
            "max_disk_mb": self.max_disk_mb,
            "quota": self.quota,
            "quota_resets": self.quota_resets,
            "operator_authorized": self.operator_authorized,
            "operator_evidence": self.operator_evidence,
            "verification_state": self.verification_state.value,
            "verification_evidence": self.verification_evidence,
            "operator_action_required": self.operator_action_required,
            "execution_proven": self.verification_state in VERIFIED_STATES,
            "federation_blockers": list(self.federation_blockers()),
            "local_blockers": list(self.local_blockers()),
            "reachable_from_this_runtime": not self.local_blockers(),
            "credential_held_by_worker": self.credential_held_by_worker,
            "reachable_only_by_dispatch_through": self.reachable_only_by_dispatch,
            "egress_note": self.egress_note,
            "inference_provable_by": self.inference_provable_by,
            "usable_without_approval": self.usable_without_approval,
            "blockers": list(self.blockers()),
            "offerings": [offering.to_dict() for offering in self.offerings],
            "notes": self.notes,
            "evidence": list(self.evidence),
            "routing_authority": self.routing_authority,
            "model_selection_authority": self.model_selection_authority,
            "admission_authority": self.admission_authority,
        }


@dataclass
class ProviderResolution:
    """What the recorded paths have to say about one model."""

    model_id: str
    exact: tuple[tuple[str, ModelOffering], ...] = field(default_factory=tuple)
    capability: tuple[tuple[str, ModelOffering], ...] = field(default_factory=tuple)
    rejected: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: The provider serves it, but something still unproven stands between the
    #: catalog row and a usable route - typically free-tier eligibility. Kept
    #: apart from `rejected` because the remedy is one probe, not a machine.
    pending: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def has_exact(self) -> bool:
        return bool(self.exact)

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "exact": [{"provider_id": p, **dict(o.to_dict())} for p, o in self.exact],
            "capability_fallback": [
                {"provider_id": p, **dict(o.to_dict())} for p, o in self.capability
            ],
            "pending_verification": {k: list(v) for k, v in sorted(self.pending.items())},
            "rejected_paths": {k: list(v) for k, v in sorted(self.rejected.items())},
        }


class ProviderRegistry:
    """The recorded execution paths. Reports capability, decides nothing."""

    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False
    admission_authority = False

    def __init__(self, providers: Iterable[ProviderRecord] = ()) -> None:
        self._providers: dict[str, ProviderRecord] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: ProviderRecord) -> ProviderRecord:
        if not provider.provider_id.strip():
            raise ProviderError("provider_id is required")
        self._providers[provider.provider_id] = provider
        return provider

    def all(self) -> tuple[ProviderRecord, ...]:
        return tuple(self._providers.values())

    def get(self, provider_id: str) -> ProviderRecord:
        try:
            return self._providers[provider_id]
        except KeyError:
            raise ProviderError(f"unknown provider {provider_id!r}") from None

    def resolve(self, model_id: str, *, free_only: bool = True) -> ProviderResolution:
        """Which paths serve this model, split by exact against substitute.

        A path whose cost or credentials rule it out lands in `rejected` with
        the reason rather than being dropped, so "nowhere serves it" and "the
        one place that serves it wants a credential we do not have" stay
        different answers.
        """
        exact: list[tuple[str, ModelOffering]] = []
        capability: list[tuple[str, ModelOffering]] = []
        rejected: dict[str, tuple[str, ...]] = {}
        pending: dict[str, tuple[str, ...]] = {}

        for provider in self._providers.values():
            offering = provider.offering_for(model_id)
            if offering is None or offering.match in {OfferingMatch.ABSENT, OfferingMatch.UNVERIFIED}:
                continue

            hard = list(provider.federation_blockers()) if free_only else []
            if hard:
                rejected[provider.provider_id] = tuple(hard)
                continue

            # Everything past here is a path the federation has. What remains is
            # whether it is *proven* usable, which is a probe, and whether this
            # container can drive it, which is neither the model's problem nor
            # the provider's.
            soft = list(provider.local_blockers())
            if free_only and offering.free_tier_eligible is False:
                soft.append(
                    f"{offering.provider_model_id} is listed but not served on this "
                    f"provider's free tier"
                )
            elif free_only and offering.free_tier_eligible is None:
                soft.append(
                    f"{offering.provider_model_id} free-tier eligibility is unverified; "
                    f"fail closed until one request on the free plan returns a completion"
                )
            if soft:
                pending[provider.provider_id] = tuple(soft)
                continue

            (exact if offering.match is OfferingMatch.EXACT else capability).append(
                (provider.provider_id, offering)
            )

        return ProviderResolution(
            model_id=model_id,
            exact=tuple(exact),
            capability=tuple(capability),
            rejected=rejected,
            pending=pending,
        )
