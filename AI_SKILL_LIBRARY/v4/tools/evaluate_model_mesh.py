from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


BENCHMARK_PATH = Path("AI_SKILL_LIBRARY/v4/model_mesh/benchmarks.yaml")
_SECRET_MARKERS = ("api_key", "apikey", "authorization", "bearer ", "secret", "private_key", "access_token")
_CONFIDENTIAL_CLASSES = {"INTERNAL", "CONFIDENTIAL"}


def load_benchmarks(root: Path) -> dict:
    path = root / BENCHMARK_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("model mesh benchmarks must be a mapping")
    domains = data.get("domains")
    if not isinstance(domains, dict) or not domains:
        raise ValueError("model mesh benchmarks require domains")
    return data


def _contains_secret_material(value: Any) -> bool:
    try:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False).lower()
    except (TypeError, ValueError):
        text = str(value).lower()
    return any(marker in text for marker in _SECRET_MARKERS)


def evaluate_case(case: dict, output: dict) -> dict:
    failures: list[str] = []
    if not isinstance(case, dict) or not isinstance(output, dict):
        return {"passed": False, "failures": ["schema_invalid"]}

    required = case.get("required_fields", [])
    if not isinstance(required, list):
        required = []
    if any(field not in output or output.get(field) in {None, ""} for field in required):
        failures.append("schema_invalid")

    data_class = str(case.get("data_class", "PUBLIC")).upper()
    privacy = str(output.get("privacy_class", "")).lower()
    if data_class in _CONFIDENTIAL_CLASSES and privacy and privacy != "confidential_safe":
        failures.append("privacy_mismatch")
    if data_class == "SECRET":
        failures.append("secret_external_execution_forbidden")

    if _contains_secret_material(output):
        failures.append("secret_material_detected")

    claims = output.get("claims", [])
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                failures.append("schema_invalid")
                continue
            if claim.get("requires_evidence") is True and not claim.get("source_refs"):
                failures.append("unsupported_fact")

    if case.get("requires_live_state") is True:
        live = output.get("live_state")
        status = str(output.get("verification_status", ""))
        refs = live.get("source_refs", []) if isinstance(live, dict) else []
        if not isinstance(live, dict) or not refs or status not in {"verified_live", "verified_current"}:
            failures.append("live_state_unverified")

    return {"passed": not failures, "failures": sorted(set(failures))}


def detect_conflicts(outputs: list[dict]) -> list[str]:
    failures: list[str] = []
    if not isinstance(outputs, list):
        return ["schema_invalid"]

    family_claimers: dict[str, set[str]] = {}
    resource_writers: dict[str, set[str]] = {}
    claim_values: dict[str, set[str]] = {}
    resolved_claims: set[str] = set()

    for index, output in enumerate(outputs):
        if not isinstance(output, dict):
            failures.append("schema_invalid")
            continue
        worker_id = str(output.get("worker_id") or f"worker-{index}")
        family = str(output.get("model_family", "")).strip().lower()
        claims = output.get("claims", [])
        if isinstance(claims, list) and claims and family:
            family_claimers.setdefault(family, set()).add(worker_id)
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                claim_id = str(claim.get("claim_id", "")).strip()
                if not claim_id:
                    continue
                value = json.dumps(claim.get("value"), sort_keys=True, ensure_ascii=False)
                claim_values.setdefault(claim_id, set()).add(value)

        writes = output.get("writes", [])
        if isinstance(writes, list):
            for write in writes:
                if not isinstance(write, dict):
                    continue
                resource_id = str(write.get("resource_id", "")).strip()
                if resource_id:
                    resource_writers.setdefault(resource_id, set()).add(worker_id)

        resolutions = output.get("resolutions", [])
        if str(output.get("role", "")).lower() in {"verifier", "checker"} and isinstance(resolutions, list):
            for resolution in resolutions:
                if not isinstance(resolution, dict):
                    continue
                claim_id = str(resolution.get("claim_id", "")).strip()
                refs = resolution.get("evidence_refs", [])
                if claim_id and isinstance(refs, list) and refs:
                    resolved_claims.add(claim_id)

    if any(len(workers) > 1 for workers in family_claimers.values()):
        failures.append("duplicate_model_family_truth_vote")
    if any(len(workers) > 1 for workers in resource_writers.values()):
        failures.append("same_resource_mutation_conflict")
    for claim_id, values in claim_values.items():
        if len(values) > 1 and claim_id not in resolved_claims:
            failures.append("unresolved_contradictory_claim")

    return sorted(set(failures))
