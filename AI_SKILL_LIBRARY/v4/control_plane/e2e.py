from __future__ import annotations

from typing import Any, Callable


#: The canonical chain. Three stages were added to close the Definition of
#: Done: the trace ran from decomposition straight to model selection, so a
#: golden run proved a model answered without proving an **AI Legion
#: specialist** was ever involved, and it ended at `warm_sleep`, so nothing
#: evidenced that the work survived the session that did it.
#:
#: Order matters and is asserted. `ai_legion` sits after decomposition and
#: before `model_mesh` because a specialist role is what the mesh selects a
#: model *for*; putting it after would make the role a label applied to a
#: choice already made. `memory_update` and `checkpoint` sit after `response`
#: because there is nothing to persist until there is an answer.
_TRACE = [
    "ingress", "task_router", "task_decomposition", "ai_legion", "model_mesh",
    "runtime_scheduler", "wake_load", "real_inference", "verifier",
    "brain_synthesis", "response", "memory_update", "checkpoint", "warm_sleep",
]
_RUNTIME_FIELDS = {
    "artifact_identity", "runtime", "runtime_version", "offline", "started_at", "ended_at",
    "load_latency_ms", "inference_latency_ms", "peak_ram_mb", "output", "raw_run_ref", "lifecycle",
}


def run_golden_e2e(
    envelope: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    ingress: Callable,
    router: Callable,
    legion: Callable,
    selector: Callable,
    runtime: Callable,
    verifier: Callable,
    synthesis: Callable,
    memory: Callable,
) -> dict[str, Any]:
    """Run the canonical control-plane trace through an injected runtime boundary.

    `legion` and `memory` are required rather than optional. An optional stage
    is one a passing run can skip, and a Definition of Done that a passing run
    can skip is not one.
    """
    route = router(envelope)
    if not isinstance(route, dict) or route.get("routed_by") != "task_router":
        raise ValueError("task_router evidence is required")
    prepared = ingress(envelope, route)

    assignment = legion(route, prepared)
    if not isinstance(assignment, dict) or not str(assignment.get("specialist_group") or "").strip():
        raise ValueError("AI Legion specialist assignment is required")
    if assignment.get("orchestration_authority") is not False:
        # Legion orchestrates specialists; it does not route and does not
        # select models. A run that let it claim either would be evidence of
        # the wrong architecture.
        raise ValueError("AI Legion must not claim orchestration authority over routing")

    selection = selector(prepared["selection_request"], candidates)
    primary = selection.get("primary_model") if isinstance(selection, dict) else None
    if not isinstance(primary, dict):
        raise ValueError("Model Mesh primary selection is required")
    execution = runtime(selection, prepared)
    failures: list[str] = []
    if not isinstance(execution, dict):
        execution = {}
        failures.append("runtime_evidence_invalid")
    missing = sorted(_RUNTIME_FIELDS - set(execution))
    if missing:
        failures.append("runtime_evidence_missing:" + ",".join(missing))
    if execution.get("real_inference") is not True or execution.get("synthetic") is not False or execution.get("fixture_only") is not False:
        failures.append("real_runtime_evidence_required")
    if execution.get("artifact_identity") != primary.get("artifact_identity"):
        failures.append("artifact_identity_mismatch")
    lifecycle = execution.get("lifecycle")
    if not isinstance(lifecycle, dict) or not all(lifecycle.get(name) is True for name in ("wake", "warm", "sleep")):
        failures.append("lifecycle_evidence_incomplete")

    verification = verifier(selection.get("verifier"), execution)
    verifier_pass = isinstance(verification, dict) and verification.get("passed") is True
    if not verifier_pass:
        failures.extend(verification.get("failures", ["verification_failed"]) if isinstance(verification, dict) else ["verification_failed"])
    real_pass = not any(item.startswith("runtime_") or item in {"real_runtime_evidence_required", "artifact_identity_mismatch", "lifecycle_evidence_incomplete"} for item in failures)
    response = synthesis(prepared, execution, verification) if real_pass and verifier_pass else None
    b2 = real_pass
    b3 = b2 and verifier_pass and response is not None
    b4 = b3 and execution.get("offline") is True and str(execution.get("runtime", "")).lower() not in {"hosted_api", "cloud_api"}

    # Persist only what a real answer produced. A checkpoint written for a run
    # that failed would be a resumable record of nothing.
    checkpoint = memory(prepared, response, verification) if response is not None else None
    continuity_failures: list[str] = []
    if response is not None:
        if not isinstance(checkpoint, dict):
            continuity_failures.append("checkpoint_not_written")
        else:
            if not str(checkpoint.get("checkpoint_id") or "").strip():
                continuity_failures.append("checkpoint_has_no_id")
            if checkpoint.get("resumable") is not True:
                continuity_failures.append("checkpoint_not_resumable")
            if checkpoint.get("memory_authority") is not False:
                continuity_failures.append("memory_claimed_authority")
    failures.extend(continuity_failures)

    return {
        "trace": list(_TRACE),
        "route": route,
        "legion": assignment,
        "checkpoint": checkpoint,
        "continuity_pass": response is not None and not continuity_failures,
        "selection": selection,
        "runtime_evidence": execution,
        "verification": verification,
        "response": response,
        "failures": sorted(set(failures)),
        "B2_pass": b2,
        "B3_pass": b3,
        "B4_pass": b4,
    }
