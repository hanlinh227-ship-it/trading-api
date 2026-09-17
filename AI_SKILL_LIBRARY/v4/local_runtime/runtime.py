"""Runtime abstraction and capability negotiation.

`RuntimeMesh.invoke(contract, claim)` is the one call the rest of the system
makes to get a model to answer. Behind it sit adapters - llama.cpp, Ollama,
vLLM, SGLang, Transformers, MLX, TGI, LMDeploy - which differ in almost every
way except the shape of that call.

Two decisions are worth stating outright.

**Observation beats the registry.** A registry entry is a claim someone made
about a model; a probe is what the runtime says about itself, right now, with
this build and this much memory. Where they disagree the observation wins, and
the disagreement is recorded in `downgrades` rather than silently smoothed
over - a model advertised at 128k context that loaded at 32k is a fact the
caller needs, not a detail to hide.

**No adapter is activated here.** `ADAPTER_TARGETS` declares the contract each
one has to meet - platforms, accelerators, what it would need to prove - and
every entry ships `activated: False`. Turning one on means proving it in a real
environment, the same way the Brain Expansion adapters are activated: in CI,
against a real install, with evidence. A table entry is not a working runtime,
and this module does not pretend otherwise.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .resilience import CircuitBreaker, FailureKind, RetryPolicy, classify_exception

#: Adapter targets and what each would have to prove before activation.
#: `activated` is False for every one of them: this table is a contract, not an
#: install. Nothing here reaches a network or a GPU until an activation run
#: turns it on with evidence.
ADAPTER_TARGETS: Mapping[str, Mapping[str, Any]] = {
    "llama.cpp": {
        "platforms": ("linux", "darwin", "windows"),
        "accelerators": ("cpu", "cuda", "metal", "rocm", "vulkan"),
        "artifact": "gguf",
        "activated": False,
        "routing_authority": False,
    },
    "ollama": {
        "platforms": ("linux", "darwin", "windows"),
        "accelerators": ("cpu", "cuda", "metal", "rocm"),
        "artifact": "ollama-model",
        "activated": False,
        "routing_authority": False,
    },
    "vllm": {
        "platforms": ("linux",),
        "accelerators": ("cuda", "rocm"),
        "artifact": "safetensors",
        "activated": False,
        "routing_authority": False,
    },
    "sglang": {
        "platforms": ("linux",),
        "accelerators": ("cuda",),
        "artifact": "safetensors",
        "activated": False,
        "routing_authority": False,
    },
    "transformers": {
        "platforms": ("linux", "darwin", "windows"),
        "accelerators": ("cpu", "cuda", "mps", "rocm"),
        "artifact": "safetensors",
        "activated": False,
        "routing_authority": False,
    },
    "mlx": {
        "platforms": ("darwin",),
        "accelerators": ("metal",),
        "artifact": "mlx",
        "activated": False,
        "routing_authority": False,
    },
    "tgi": {
        "platforms": ("linux",),
        "accelerators": ("cuda", "rocm"),
        "artifact": "safetensors",
        "activated": False,
        "routing_authority": False,
    },
    "lmdeploy": {
        "platforms": ("linux",),
        "accelerators": ("cuda",),
        "artifact": "safetensors",
        "activated": False,
        "routing_authority": False,
    },
}


class InvocationStatus(str, Enum):
    OK = "OK"
    REFUSED = "REFUSED"        # negotiation said no; nothing was called
    FAILED = "FAILED"          # every eligible runtime was tried and failed
    NO_RUNTIME = "NO_RUNTIME"  # there was nothing to try


@dataclass(frozen=True)
class RuntimeCapability:
    """What a runtime reports about itself, right now."""

    runtime: str
    runtime_version: str
    loaded_models: tuple[str, ...]
    available_memory_mb: int | None
    context_limit: int | None
    modalities: frozenset[str]
    tool_support: bool
    quantizations: frozenset[str]
    healthy: bool
    latency_p50_ms: float | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "runtime": self.runtime,
            "runtime_version": self.runtime_version,
            "loaded_models": list(self.loaded_models),
            "available_memory_mb": self.available_memory_mb,
            "context_limit": self.context_limit,
            "modalities": sorted(self.modalities),
            "tool_support": self.tool_support,
            "quantizations": sorted(self.quantizations),
            "healthy": self.healthy,
            "latency_p50_ms": self.latency_p50_ms,
        }


@dataclass(frozen=True)
class RegistryClaim:
    """What the registry says about a model - optimistic until observed."""

    model_id: str
    context_limit: int
    modalities: frozenset[str]
    tool_support: bool
    zero_cost: bool = True


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    model_id: str
    payload: Mapping[str, Any]
    context_tokens: int = 0
    modality: str = "text"
    requires_tools: bool = False
    max_output_tokens: int | None = None
    timeout_seconds: float = 120.0
    free_only: bool = True


@dataclass(frozen=True)
class NegotiationResult:
    accepted: bool
    reason: str
    effective_context_limit: int | None = None
    effective_modalities: frozenset[str] = frozenset()
    warm: bool = False
    #: Where the observed runtime contradicted the registry claim.
    downgrades: tuple[str, ...] = ()


@dataclass(frozen=True)
class InvocationResult:
    task_id: str
    status: InvocationStatus
    reason: str
    runtime: str | None = None
    output: Any = None
    attempted: tuple[str, ...] = ()
    failures: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is InvocationStatus.OK


def negotiate(
    task_contract: TaskContract, claim: RegistryClaim, capability: RuntimeCapability
) -> NegotiationResult:
    """Reconcile what the registry promised with what the runtime actually has."""
    downgrades: list[str] = []

    if not capability.healthy:
        return NegotiationResult(accepted=False, reason=f"runtime {capability.runtime} health probe is failing")

    if task_contract.free_only and not claim.zero_cost:
        return NegotiationResult(
            accepted=False,
            reason=f"{claim.model_id} is not zero-cost eligible under FREE_ONLY; no paid fallback",
        )

    limit = claim.context_limit
    if capability.context_limit is not None and capability.context_limit < limit:
        downgrades.append(
            f"context limit: registry claimed {limit}, runtime reports {capability.context_limit}"
        )
        limit = capability.context_limit
    if task_contract.context_tokens > limit:
        return NegotiationResult(
            accepted=False,
            reason=f"context {task_contract.context_tokens} exceeds the effective limit {limit}",
            effective_context_limit=limit,
            downgrades=tuple(downgrades),
        )

    modalities = claim.modalities & capability.modalities
    if claim.modalities - capability.modalities:
        downgrades.append(
            f"modalities: registry claimed {sorted(claim.modalities)}, "
            f"runtime offers {sorted(capability.modalities)}"
        )
    if task_contract.modality not in modalities:
        return NegotiationResult(
            accepted=False,
            reason=f"modality {task_contract.modality!r} is not available on {capability.runtime}",
            effective_context_limit=limit,
            effective_modalities=modalities,
            downgrades=tuple(downgrades),
        )

    if task_contract.requires_tools and not capability.tool_support:
        if claim.tool_support:
            downgrades.append("tool support: registry claimed true, runtime reports false")
        return NegotiationResult(
            accepted=False,
            reason=f"tool support is required but {capability.runtime} does not provide it",
            effective_context_limit=limit,
            effective_modalities=modalities,
            downgrades=tuple(downgrades),
        )

    return NegotiationResult(
        accepted=True,
        reason=f"negotiated with {capability.runtime} {capability.runtime_version}",
        effective_context_limit=limit,
        effective_modalities=modalities,
        warm=task_contract.model_id in capability.loaded_models,
        downgrades=tuple(downgrades),
    )


class ModelRuntimeAdapter(ABC):
    """The whole surface a runtime has to implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def probe(self) -> RuntimeCapability:
        """Report live capability. May raise; the mesh treats that as unhealthy."""

    @abstractmethod
    def execute(self, task_contract: TaskContract, capability: RuntimeCapability) -> Any:
        """Run the contract. May raise; the mesh classifies and fails over."""


class RuntimeMesh:
    """Runs a contract against the first runtime that can take it.

    Holds no routing or selection authority: `task_router` decided the route and
    the Model Mesh nominated the model before this was called. All this decides
    is which *runtime* serves an already-chosen model, and it will not reach for
    a paid one when the free ones are down.
    """

    #: Invariants, asserted by tests rather than left to convention.
    routing_authority = False
    reasoning_authority = False
    memory_authority = False
    model_selection_authority = False

    def __init__(
        self,
        adapters: Iterable[ModelRuntimeAdapter],
        *,
        retry_policy: RetryPolicy | None = None,
        breaker_factory=CircuitBreaker,
    ) -> None:
        self._adapters: list[ModelRuntimeAdapter] = list(adapters)
        self._retry = retry_policy or RetryPolicy()
        self._breakers: dict[str, CircuitBreaker] = {
            adapter.name: breaker_factory() for adapter in self._adapters
        }

    def breaker(self, name: str) -> CircuitBreaker:
        return self._breakers[name]

    def _capability(self, adapter: ModelRuntimeAdapter) -> RuntimeCapability | None:
        try:
            return adapter.probe()
        except Exception:  # noqa: BLE001 - a runtime that cannot answer a probe is just unhealthy
            return None

    def invoke(
        self, task_contract: TaskContract, claim: RegistryClaim, *, now: float
    ) -> InvocationResult:
        """Serve the contract, or report why nothing could. Never raises."""
        if not self._adapters:
            return InvocationResult(
                task_id=task_contract.task_id,
                status=InvocationStatus.NO_RUNTIME,
                reason="no runtime adapter is registered",
            )

        # Probe everything first so a warm runtime is preferred over a cold one:
        # the model already being resident usually dwarfs every other difference.
        candidates: list[tuple[ModelRuntimeAdapter, RuntimeCapability, NegotiationResult]] = []
        refusals: dict[str, str] = {}
        negotiation_refused: set[str] = set()
        for adapter in self._adapters:
            breaker = self._breakers[adapter.name]
            if not breaker.allow(now=now):
                refusals[adapter.name] = f"circuit breaker {breaker.state.value}"
                continue
            capability = self._capability(adapter)
            if capability is None:
                refusals[adapter.name] = "capability probe failed"
                continue
            negotiation = negotiate(task_contract, claim, capability)
            if not negotiation.accepted:
                # A negotiation refusal is about the contract, not the runtime's
                # health - tripping the breaker for it would punish a runtime
                # that is working perfectly well.
                refusals[adapter.name] = negotiation.reason
                negotiation_refused.add(adapter.name)
                continue
            candidates.append((adapter, capability, negotiation))

        candidates.sort(key=lambda row: (not row[2].warm, row[1].latency_p50_ms or float("inf")))

        if not candidates:
            # REFUSED means the *contract* was turned away by every runtime -
            # a caller can act on that by changing the contract. When runtimes
            # were merely unreachable or broken, the contract was fine and
            # nothing to change, so that is a FAILED.
            contract_refused = bool(refusals) and negotiation_refused == set(refusals)
            return InvocationResult(
                task_id=task_contract.task_id,
                status=InvocationStatus.REFUSED if contract_refused else InvocationStatus.FAILED,
                reason=(
                    "no runtime could take this contract"
                    if contract_refused
                    else "no runtime was available; no paid fallback exists"
                ),
                attempted=(),
                failures=refusals,
            )

        attempted: list[str] = []
        for adapter, capability, _negotiation in candidates:
            breaker = self._breakers[adapter.name]
            attempted.append(adapter.name)
            for attempt in range(1, self._retry.max_attempts + 1):
                if attempt > 1 and not breaker.allow(now=now):
                    break
                try:
                    output = adapter.execute(task_contract, capability)
                except Exception as exc:  # noqa: BLE001 - one runtime dying is not the brain dying
                    kind = classify_exception(exc)
                    breaker.record_failure(kind, now=now)
                    refusals[adapter.name] = f"{kind.value}: {exc}"
                    if self._retry.should_retry(kind, attempt=attempt):
                        continue
                    if not self._retry.should_failover(kind):
                        return InvocationResult(
                            task_id=task_contract.task_id,
                            status=InvocationStatus.FAILED,
                            reason=f"{kind.value} is not recoverable by failover: {exc}",
                            attempted=tuple(attempted),
                            failures=refusals,
                        )
                    break
                else:
                    breaker.record_success(now=now)
                    return InvocationResult(
                        task_id=task_contract.task_id,
                        status=InvocationStatus.OK,
                        reason=f"served by {adapter.name}",
                        runtime=adapter.name,
                        output=output,
                        attempted=tuple(attempted),
                        failures=refusals,
                    )

        return InvocationResult(
            task_id=task_contract.task_id,
            status=InvocationStatus.FAILED,
            reason="every eligible runtime failed; no paid fallback exists",
            attempted=tuple(attempted),
            failures=refusals,
        )

    def health(self, *, now: float) -> Mapping[str, Mapping[str, Any]]:
        """One report covering every adapter, whether or not it is answering."""
        report: dict[str, Mapping[str, Any]] = {}
        for adapter in self._adapters:
            capability = self._capability(adapter)
            report[adapter.name] = {
                "breaker": self._breakers[adapter.name].to_dict(now=now),
                "capability": capability.to_dict() if capability else None,
                "reachable": capability is not None,
            }
        return report
