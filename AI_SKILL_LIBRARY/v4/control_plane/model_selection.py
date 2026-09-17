from __future__ import annotations

from copy import deepcopy
from typing import Any


_REQUIRED_SELECTION_FIELDS = {
    "task_id",
    "domain",
    "required_capabilities",
    "privacy",
    "context",
    "latency_budget",
    "resource_budget",
    "execution_profile",
    "verifier_requirement",
}
_PROFILE_CAPS = {"FAST": 1, "STANDARD": 2, "DEEP": 4}
_ADMISSION_TRUE = ("license_verified", "provenance_verified", "safe_format_verified", "pickle_safe")


def _require_admitted(record: dict[str, Any]) -> None:
    admission = record.get("admission_evidence")
    if (
        record.get("lifecycle_state") != "AVAILABLE"
        or record.get("model_mesh_local_candidate_eligible") is not True
        or not isinstance(admission, dict)
        or any(admission.get(field) is not True for field in _ADMISSION_TRUE)
        or admission.get("trust_remote_code_required") is not False
        or admission.get("custom_code_required") is not False
        or admission.get("malware_scan_status") != "pass"
        or admission.get("quarantine_status") != "clear"
    ):
        raise ValueError("model admission evidence is not clear")


def project_local_candidate(record: dict[str, Any], runtime_evidence: dict[str, Any]) -> dict[str, Any]:
    """Project an admitted governance record into a generic Model Mesh candidate.

    Runtime evidence is consumed, never manufactured. This function has no
    runtime or routing authority.
    """
    if not isinstance(record, dict) or not isinstance(runtime_evidence, dict):
        raise TypeError("record and runtime_evidence must be mappings")
    _require_admitted(record)
    identity = record.get("artifact_identity")
    if not isinstance(identity, dict) or not identity.get("sha256"):
        raise ValueError("artifact identity is required")
    health = runtime_evidence.get("health")
    resource = runtime_evidence.get("resource")
    benchmark = runtime_evidence.get("benchmark")
    runtime = runtime_evidence.get("runtime")
    if not isinstance(health, dict) or health.get("state") not in {"healthy", "degraded"}:
        raise ValueError("current runtime health evidence is required")
    if not isinstance(resource, dict) or resource.get("artifact_size_bytes") != identity.get("size_bytes"):
        raise ValueError("resource evidence must bind the artifact")
    if not isinstance(runtime, dict) or runtime.get("supported") is not True:
        raise ValueError("runtime support evidence is required")
    if not isinstance(benchmark, dict):
        raise ValueError("benchmark evidence block is required")

    measured_caps = benchmark.get("capabilities") if isinstance(benchmark.get("capabilities"), dict) else {}
    declared_caps = record.get("capabilities") if isinstance(record.get("capabilities"), dict) else {}
    capabilities: dict[str, dict[str, Any]] = {}
    for name in sorted(set(declared_caps) | set(measured_caps)):
        measured = measured_caps.get(name)
        if isinstance(measured, dict) and measured.get("supported") in {True, False}:
            score = measured.get("score")
            capabilities[name] = {
                "supported": measured["supported"],
                "score": score if isinstance(score, (int, float)) and not isinstance(score, bool) else None,
                "evidence": list(measured.get("evidence", [])),
            }
        else:
            capabilities[name] = {"supported": "unknown", "score": None, "evidence": []}

    family = str(identity.get("family", "")).strip()
    lineage = record.get("lineage") if isinstance(record.get("lineage"), dict) else {}
    lineage_id = str(lineage.get("source_model_id") or record.get("base_model") or identity.get("model_id"))
    return {
        "candidate_key": f"local_runtime:{identity['sha256']}",
        "provider_id": "local_runtime",
        "model_id": identity.get("model_id"),
        "model_family": family,
        "family_id": family,
        "lineage_id": lineage_id,
        "independence_score": 1.0 if lineage.get("conversion_verified") is True else 0.0,
        "artifact_identity": deepcopy(identity),
        "capabilities": capabilities,
        "privacy": record.get("privacy_class", "unknown"),
        "zero_cost": record.get("paid_token_required") is False,
        "offline_ready": runtime.get("offline_ready") is True and record.get("offline_eligible") is True,
        "runtime_support": list(record.get("runtime_support", [])),
        "resource_evidence": deepcopy(resource),
        "health_evidence": deepcopy(health),
        "benchmark_evidence": deepcopy(benchmark),
        "warm_state": runtime.get("warm_state") is True,
        "load_cost_ms": runtime.get("load_cost_ms"),
        "latency_ms": runtime.get("latency_ms"),
    }


def validate_selection_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise TypeError("selection request must be a mapping")
    missing = sorted(field for field in _REQUIRED_SELECTION_FIELDS if field not in request)
    if missing:
        raise ValueError("missing selection fields: " + ", ".join(missing))
    profile = str(request.get("execution_profile", "")).upper()
    if profile not in _PROFILE_CAPS:
        raise ValueError("execution_profile must be FAST, STANDARD, or DEEP")
    if not isinstance(request.get("required_capabilities"), list) or not request["required_capabilities"]:
        raise ValueError("required_capabilities must be non-empty")
    return deepcopy(request)


def _eligible(candidate: dict[str, Any], request: dict[str, Any]) -> bool:
    if candidate.get("zero_cost") is not True or candidate.get("offline_ready") is not True:
        return False
    if candidate.get("health_evidence", {}).get("state") != "healthy":
        return False
    if request["privacy"] in {"CONFIDENTIAL", "SECRET"} and candidate.get("privacy") != "confidential_safe":
        return False
    resource = candidate.get("resource_evidence", {})
    budget = request.get("resource_budget", {})
    if resource.get("ram_required_mb") is None or resource.get("ram_required_mb") > budget.get("ram_mb", 0):
        return False
    if resource.get("vram_required_mb") is None or resource.get("vram_required_mb") > budget.get("vram_mb", 0):
        return False
    for name in request["required_capabilities"]:
        cap = candidate.get("capabilities", {}).get(name, {})
        if cap.get("supported") is not True or not cap.get("evidence"):
            return False
    return True


def _quality(candidate: dict[str, Any], required: list[str]) -> float:
    scores = [candidate["capabilities"][name].get("score") for name in required]
    numeric = [float(score) for score in scores if isinstance(score, (int, float)) and not isinstance(score, bool)]
    bench = candidate.get("benchmark_evidence", {}).get("quality")
    if isinstance(bench, (int, float)) and not isinstance(bench, bool):
        numeric.append(float(bench))
    return min(numeric) if numeric else 0.0


def select_models(request: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    request = validate_selection_request(request)
    eligible = [deepcopy(row) for row in candidates if isinstance(row, dict) and _eligible(row, request)]
    if not eligible:
        raise ValueError("no eligible Model Mesh candidate")
    required = request["required_capabilities"]
    eligible.sort(key=lambda row: (-_quality(row, required), row.get("candidate_key", "")))
    best_quality = _quality(eligible[0], required)
    warm_peers = [row for row in eligible if row.get("warm_state") is True and best_quality - _quality(row, required) <= 0.03]
    primary = warm_peers[0] if warm_peers else eligible[0]

    cap = _PROFILE_CAPS[request["execution_profile"].upper()]
    selected = [primary]
    fallbacks: list[dict[str, Any]] = []
    for row in eligible:
        if row.get("candidate_key") == primary.get("candidate_key"):
            continue
        same_lineage = row.get("lineage_id") in {item.get("lineage_id") for item in selected}
        too_dependent = float(row.get("independence_score", 0.0) or 0.0) <= 0.0 and same_lineage
        if same_lineage or too_dependent:
            fallbacks.append(row)
        elif len(selected) < cap:
            selected.append(row)
        else:
            fallbacks.append(row)

    return {
        "primary_model": selected[0],
        "supporting_models": selected[1:],
        "verifier": request["verifier_requirement"],
        "fallback_chain": fallbacks,
        "evidence_refs": sorted({ref for row in selected for ref in row.get("benchmark_evidence", {}).get("evidence_refs", [])}),
        "resource_plan": {
            "profile": request["execution_profile"].upper(),
            "max_concurrent_models": cap,
            "selected": [row.get("candidate_key") for row in selected],
        },
    }
