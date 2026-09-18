"""B2: the canonical route from ingress to real local inference.

The path a request actually takes:

    ingress -> task_router -> Model Mesh -> local candidate
            -> runtime projection -> scheduler -> llama.cpp -> Qwen

Every stage is the canonical one. The router decision comes from
`v4/stable/router.yaml`, and candidate selection comes from the Model Mesh's own
`normalize_candidate` / `eligible_free_candidate` / `score_candidate` - this
module calls them, it does not reimplement their judgement.

The rule that shapes the whole design: **ingress never names a model.** It
carries a request and, at most, a domain hint. The local model becomes the
answer only because the mesh's ordinary filters - permission, zero-cost
entitlement, quota headroom, context window, capability floor - left it standing
and its score came out on top. Wiring ingress straight to Qwen would produce the
same tokens and prove nothing, so a test asserts that a request whose
capabilities the candidate cannot meet selects nothing at all.

Authority is unchanged: `task_router` routes, the Model Mesh selects, this lane
executes. Nothing here decides which of those it is allowed to be.
"""

from __future__ import annotations

import datetime
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from AI_SKILL_LIBRARY.v4.tools import model_mesh as mesh  # noqa: E402

from .backends.llama_cpp_python import LlamaCppPythonBackend, detect_llama_cpp_python  # noqa: E402
from .evidence import EvidenceRecorder, PeakSampler  # noqa: E402
from .identity import from_record  # noqa: E402
from .projection import project_record  # noqa: E402
from .lifecycle import ModelState  # noqa: E402
from .reconciliation import ENTRY_STATE  # noqa: E402
from .residency import ResidencyState  # noqa: E402
from .resources import detect_resources  # noqa: E402
from .runtime import TaskContract  # noqa: E402
from .scheduler import (  # noqa: E402
    PlacementAction,
    Priority,
    Privacy,
    QualityTier,
    RuntimeSlot,
    TaskRequest,
    plan_placement,
)
from .staging import resolve_cached  # noqa: E402

ROUTER_REL = "AI_SKILL_LIBRARY/v4/stable/router.yaml"

#: Where a locally-resident model is offered from. Not a network provider.
LOCAL_PROVIDER_ID = "local_runtime"


class RouteError(RuntimeError):
    """The canonical route could not be completed."""


@dataclass(frozen=True)
class StageRecord:
    stage: str
    ok: bool
    detail: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Mapping[str, Any]:
        return {"stage": self.stage, "ok": self.ok, "detail": self.detail, "data": dict(self.data)}


@dataclass(frozen=True)
class RouteResult:
    request_id: str
    ok: bool
    reason: str
    stages: tuple[StageRecord, ...] = ()
    output: str | None = None
    evidence: Mapping[str, Any] | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "request_id": self.request_id,
            "canonical_route_ok": self.ok,
            "reason": self.reason,
            "stages": [s.to_dict() for s in self.stages],
            "output": self.output,
            "execution_evidence": (self.evidence or {}).get("execution_evidence"),
            # Restated per result so no consumer has to infer it.
            "routing_authority": "task_router",
            "model_selection_authority": "model_mesh",
            "runtime_residency_authority": "claude_local_runtime",
        }


# -- stage 1: task_router -------------------------------------------------


def route_request(text: str, *, root: Path, domain_hint: str | None = None) -> Mapping[str, Any]:
    """Resolve domain and primary skill from the canonical router config.

    Reads `stable/router.yaml` rather than deciding anything itself. No model
    is named at this stage and none can be - the router's vocabulary is domains
    and skills.
    """
    config = yaml.safe_load((Path(root) / ROUTER_REL).read_text(encoding="utf-8"))
    routes = config.get("domain_routes") or {}
    selection = config.get("selection") or {}
    fallback_skill = str(selection.get("fallback_primary_skill") or "core_reasoning")

    domain = domain_hint if domain_hint in routes else None
    if domain is None:
        # Cheap lexical routing over the canonical domain vocabulary. The point
        # is that the choice comes from router.yaml's domains, not from a model.
        #
        # Matched on whole words. Substring matching routed "the capital of
        # France" to engineering, because "cap-api-tal" contains "api".
        import re

        words = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
        best, best_hits = None, 0
        for name, skills in routes.items():
            hits = sum(
                1 for skill in skills
                if set(re.findall(r"[a-z0-9]+", skill.replace("_", " "))) <= words
            )
            if hits > best_hits:
                best, best_hits = name, hits
        domain = best or "core"

    skills = list(routes.get(domain) or [])
    primary_skill = fallback_skill if fallback_skill in skills else (skills[0] if skills else fallback_skill)
    return {
        "router": str((config.get("authority") or {}).get("mandatory_router", "task_router")),
        "domain": domain,
        "primary_skill": primary_skill,
        "model_named_at_ingress": False,
    }


# -- stage 2: Model Mesh --------------------------------------------------


def as_mesh_candidate(profile: Any, record: Mapping[str, Any], *, observed_at: str) -> Mapping[str, Any]:
    """Project an admitted local model into a Model Mesh candidate.

    Built through the mesh's own `normalize_candidate`, so the candidate is
    subject to exactly the same normalisation and defaults as any other. A
    locally-resident, already-acquired model carries
    `owned_hardware_zero_marginal` cost: running it spends electricity, not
    tokens.
    """
    # The evidence string names where the score came from. It used to be the
    # constant "registry_declared", which described a measured score and a
    # made-up one identically - exactly the distinction the mesh needs in order
    # to weigh a candidate honestly.
    #
    # `supported` follows the same rule, and it is the stricter half: the mesh
    # treats a capability as usable only when `supported is True`, so asserting
    # it is asserting that the model was shown to have the capability. An
    # unmeasured capability stays "unknown" - not False, which would claim the
    # model was tested and failed, and not True, which would be the fabrication
    # this whole path exists to prevent.
    measurements = record.get("capability_evidence") or {}
    if not isinstance(measurements, Mapping):
        measurements = {}
    capabilities = {}
    for name, score in (record.get("capabilities") or {}).items():
        row = measurements.get(name)
        if isinstance(row, Mapping) and str(row.get("artifact_sha256") or "") == str(
            (record.get("artifact_identity") or {}).get("sha256") or ""
        ):
            capabilities[name] = {
                "supported": True,
                # Measured, digest-bound, so it competes at its real score
                # rather than being capped like a self-reported one.
                "evidence_state": "VERIFIED",
                "score": float(score),
                "evidence": [
                    f"measured:{row.get('benchmark_id')}@{row.get('benchmark_version')}"
                    f"+{str(row.get('suite_hash') or '')[:12]}",
                    str(row.get("evidence_ref") or ""),
                ],
                "verified_at": str(row.get("measured_at") or "") or None,
            }
        else:
            capabilities[name] = {
                "supported": "unknown",
                "evidence_state": "PROVISIONAL",
                "score": float(score),
                "evidence": ["registry_declared"],
                "verified_at": None,
            }
    raw = {
        "model_id": profile.model_id,
        "model_family": profile.family or "",
        "model_variant": profile.variant or "",
        "provider_class": "Q",
        "endpoint_family": "other",
        "free_status": "recurring",
        "free_verified_at": observed_at,
        "zero_cost": {
            "eligible": True,
            "basis": "owned_hardware_zero_marginal",
            "price_verified_at": observed_at,
        },
        "quota_scope": "account",
        "quota_dimensions": ["requests"],
        "reset_semantics": "rolling",
        # Values must come from the mesh's own vocabularies. "private" and
        # "permitted" are not in them and silently normalise to "unknown",
        # which the FREE_ONLY gate then rejects - a locally-resident model that
        # never leaves the host is `confidential_safe`, and an unbenchmarked one
        # is for `evaluation`, not production.
        "privacy_class": "confidential_safe",
        "usage_terms": "evaluation",
        "health": "healthy",
        "context_window": profile.context_limit,
        "capabilities": capabilities,
        "data_training_allowed_by_provider": False,
        "source_evidence": list(record.get("source_evidence") or []),
    }
    return mesh.normalize_candidate(LOCAL_PROVIDER_ID, raw, observed_at=observed_at)


def mesh_select(
    candidates: Sequence[Mapping[str, Any]],
    *,
    domain: str,
    primary_skill: str,
    data_class: str = "PUBLIC",
    context_tokens: int = 0,
) -> tuple[Mapping[str, Any] | None, list[str]]:
    """Select through the mesh's own filters and scoring. Never hardcodes.

    Returns the winner and the reasons every rejected candidate was dropped, so
    a selection of `None` is explainable rather than merely empty.
    """
    requirements = mesh.required_capabilities(domain, primary_skill)
    config = mesh._load_domain_capabilities()
    rejections: list[str] = []
    scored: list[tuple[float, Mapping[str, Any]]] = []

    for candidate in candidates:
        key = f"{candidate.get('provider_id')}:{candidate.get('model_id')}"
        if not mesh.eligible_free_candidate(candidate, data_class=data_class):
            rejections.append(f"{key}: not a zero-cost eligible candidate for {data_class}")
            continue
        window = candidate.get("context_window")
        if context_tokens and (not isinstance(window, int) or window < context_tokens):
            rejections.append(f"{key}: context window {window} below required {context_tokens}")
            continue
        if not mesh._passes_capability_floor(candidate, requirements, config):
            rejections.append(f"{key}: below the capability floor for {domain}/{primary_skill}")
            continue
        # A locally-resident model has no provider quota to run down - the
        # constraint is RAM, and that is the scheduler's job, not the mesh's.
        # Full headroom is the true value here, not a flattering one.
        #
        # Reputation is the mesh's own neutral default. This lane has no
        # operating history for a model it has just admitted, and inventing a
        # high reputation for the only candidate would rig a comparison that
        # currently has nothing to compare against - and would keep rigging it
        # once network candidates appear beside it.
        scored.append((
            mesh.score_candidate(
                candidate,
                requirements=requirements,
                quota_headroom=1.0,
                reputation=0.5,
            ),
            candidate,
        ))

    if not scored:
        return None, rejections
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1], rejections


# -- the whole route ------------------------------------------------------


def run_canonical_route(
    text: str,
    *,
    root: Path,
    cache: Path,
    max_tokens: int = 32,
    domain_hint: str | None = None,
    model_id: str | None = None,
) -> RouteResult:
    """Ingress to real tokens, through every canonical stage. Never raises."""
    from .projection import load_registry

    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    request_id = f"b2-{int(time.time())}"
    stages: list[StageRecord] = []

    def fail(stage: str, detail: str, **data: Any) -> RouteResult:
        stages.append(StageRecord(stage=stage, ok=False, detail=detail, data=data))
        return RouteResult(request_id=request_id, ok=False, reason=f"{stage}: {detail}",
                           stages=tuple(stages))

    try:
        # 1. ingress — carries a request, never a model.
        stages.append(StageRecord(
            stage="ingress", ok=True, detail="request accepted",
            data={"prompt_chars": len(text or ""), "model_named_at_ingress": False},
        ))

        # 2. task_router
        routed = route_request(text, root=root, domain_hint=domain_hint)
        stages.append(StageRecord(stage="task_router", ok=True,
                                  detail=f"{routed['domain']}/{routed['primary_skill']}", data=routed))

        # 3. admitted local candidates, from governance
        registry = load_registry(root)
        records = [r for r in (registry.get("models") or []) if isinstance(r, Mapping)]
        if model_id:
            records = [r for r in records if str(r.get("model_id")) == model_id]
        admitted: list[tuple[Any, Mapping[str, Any]]] = []
        for record in records:
            projected = project_record(record, available_runtimes=["llama.cpp"])
            if projected.placeable and projected.profile is not None:
                admitted.append((projected.profile, record))
        if not admitted:
            return fail("governance_admission", "no admitted local candidate")
        stages.append(StageRecord(stage="governance_admission", ok=True,
                                  detail=f"{len(admitted)} admitted",
                                  data={"model_ids": [p.model_id for p, _ in admitted]}))

        # 4. Model Mesh selection — the mesh's own filters decide.
        candidates = [as_mesh_candidate(p, r, observed_at=observed_at) for p, r in admitted]
        winner, rejections = mesh_select(
            candidates, domain=routed["domain"], primary_skill=routed["primary_skill"]
        )
        if winner is None:
            return fail("model_mesh", "mesh selected no candidate", rejections=rejections)
        selected_id = winner.get("model_id")
        stages.append(StageRecord(stage="model_mesh", ok=True, detail=f"selected {selected_id}",
                                  data={"selected": selected_id, "rejections": rejections,
                                        "selection_authority": "model_mesh"}))

        profile, record = next((p, r) for p, r in admitted if p.model_id == selected_id)
        identity, _ = from_record(record)

        # 5. artifact must be present and still verify
        artifact = resolve_cached(cache, record, verify=True)
        if artifact is None:
            return fail("artifact", "no verified artifact cached for the selected model")
        stages.append(StageRecord(stage="artifact", ok=True, detail="verified from cache",
                                  data={"sha256": identity.artifact_sha256}))

        # 6. scheduler placement
        snapshot = detect_resources(disk_path=str(cache))
        # The measured footprint from B1 is the requirement here; the registry
        # still carries null, and this stays host-specific evidence.
        from dataclasses import replace as _replace
        # 2048 MB is a slot size chosen to sit above B1's measured 1825.36 MB
        # peak on this host - a requirement derived from a measurement, not the
        # measurement itself, and not a registry claim. The registry still
        # carries null for minimum_ram_gb.
        measured = _replace(profile, ram_mb=2048, vram_mb=None)
        decision = plan_placement(
            TaskRequest(task_id=request_id, priority=Priority.P1_INTERACTIVE,
                        quality_tier=QualityTier.FAST, privacy=Privacy.INTERNAL,
                        required_capabilities=frozenset(), free_only=True),
            # CACHED, not the AVAILABLE entry state. The artifact was verified
            # on disk two stages ago, and telling the scheduler otherwise made
            # it plan an ACQUIRE - a 300-second download budget for a file that
            # is already there. The scheduler was right; the input was a lie.
            [RuntimeSlot(model=measured, state=ModelState.CACHED)], snapshot,
        )
        if not decision.admitted:
            return fail("scheduler", decision.reason, rejected=dict(decision.rejected))
        placement = decision.placements[0]
        stages.append(StageRecord(stage="scheduler", ok=True, detail=placement.action.value,
                                  data={"runtime": placement.runtime,
                                        "estimated_start_s": placement.estimated_start_s}))

        # 7. runtime — real llama.cpp, real tokens
        backend_identity = detect_llama_cpp_python()
        backend = LlamaCppPythonBackend(backend_identity)
        if not backend.healthy():
            return fail("runtime", "no real llama.cpp runtime available")

        recorder = EvidenceRecorder(admitted_at=time.monotonic())
        recorder.describe(
            request_id=request_id, task_id=request_id, worker_id="local",
            model_id=identity.model_id, model_revision=identity.immutable_revision,
            artifact_sha256=identity.artifact_sha256, artifact_fingerprint=identity.fingerprint,
            actual_quantization=identity.quantization, runtime_id=backend.name,
            runtime_version=backend_identity.backend_version, backend="llama.cpp",
            backend_version=backend_identity.backend_version,
            # No runtime_health here. It was a hardcoded "healthy" that
            # ExecutionEvidence has no field for; a constant self-report is not
            # evidence anyway. Health shows up as a failure_type when it fails.
            placement_action=placement.action.value,
        )
        recorder.begin(cold_or_warm="COLD", placement_action=placement.action.value)
        with PeakSampler() as sampler:
            backend.load(identity.model_id, artifact,
                         context_limit=min(int(record.get("context_window") or 2048), 4096),
                         quantization=identity.quantization)
            recorder.load_finished()
            recorder.inference_started()
            result = backend.execute(
                TaskContract(task_id=request_id, model_id=identity.model_id,
                             payload={"prompt": text}, max_output_tokens=max_tokens,
                             timeout_seconds=600.0),
                backend.probe(),
            )
        evidence = recorder.finish(
            peak_ram_mb=sampler.peak_mb, peak_vram_mb=0.0 if not snapshot.gpus else None,
            tokens_input=result.get("tokens_input"), tokens_output=result.get("tokens_output"),
        )
        backend.unload(identity.model_id)
        stages.append(StageRecord(
            stage="runtime", ok=True, detail="real tokens generated",
            data={"inference_latency_ms": result.get("inference_latency_ms"),
                  "tokens_output": result.get("tokens_output"),
                  "residency": [ResidencyState.READY.value, ResidencyState.WARM.value,
                                ResidencyState.READY.value]},
        ))
        return RouteResult(request_id=request_id, ok=True,
                           reason="canonical route completed with real inference",
                           stages=tuple(stages), output=result["text"],
                           evidence=evidence.to_dict())
    except Exception as exc:  # noqa: BLE001 - a route failure is evidence, not a crash
        return fail("unhandled", f"{type(exc).__name__}: {exc}")
