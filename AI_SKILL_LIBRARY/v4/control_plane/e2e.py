from __future__ import annotations

from typing import Any, Callable


_TRACE = [
    "ingress", "task_router", "task_decomposition", "model_mesh",
    "runtime_scheduler", "wake_load", "real_inference", "verifier",
    "brain_synthesis", "response", "warm_sleep",
]
_RUNTIME_FIELDS = {
    "artifact_identity", "runtime", "runtime_version", "started_at", "ended_at",
    "load_latency_ms", "inference_latency_ms", "peak_ram_mb", "output", "raw_run_ref", "lifecycle",
}


def run_golden_e2e(
    envelope: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    ingress: Callable,
    router: Callable,
    selector: Callable,
    runtime: Callable,
    verifier: Callable,
    synthesis: Callable,
) -> dict[str, Any]:
    """Run the canonical control-plane trace through an injected runtime boundary."""
    route = router(envelope)
    if not isinstance(route, dict) or route.get("routed_by") != "task_router":
        raise ValueError("task_router evidence is required")
    prepared = ingress(envelope, route)
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
    b4 = b3 and str(execution.get("runtime", "")).lower() not in {"hosted_api", "cloud_api"}
    return {
        "trace": list(_TRACE),
        "route": route,
        "selection": selection,
        "runtime_evidence": execution,
        "verification": verification,
        "response": response,
        "failures": sorted(set(failures)),
        "B2_pass": b2,
        "B3_pass": b3,
        "B4_pass": b4,
    }
