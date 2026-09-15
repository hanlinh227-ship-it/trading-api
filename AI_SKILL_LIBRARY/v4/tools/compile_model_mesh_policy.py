"""Compile the canonical Model Mesh policy into a runtime contract.

`AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml` is the checkpoint-declared
authority for parallelism and selection. Domain capability weights and the
Phase A capability-evidence rollout policy are compiled alongside it so the
Worker, CI and release gates consume one deterministic contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

REQUIRED_PROFILES = ("FAST", "STANDARD", "DEEP")
DEFAULT_POLICY = "AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml"
DEFAULT_DOMAIN_CAPABILITIES = "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml"
DEFAULT_OUTPUT = "AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-policy.json"


def compile_policy(root: Path, *, policy_path: Path, capabilities_path: Path, output: Path) -> dict:
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}

    errors: list[str] = []

    if policy.get("mode") != "FREE_ONLY":
        errors.append("mode must be FREE_ONLY")
    if policy.get("paid_fallback") != "disabled":
        errors.append("paid_fallback must be disabled")
    if policy.get("routing_authority") is not False:
        errors.append("routing_authority must be false")
    if policy.get("reasoning_authority") is not False:
        errors.append("reasoning_authority must be false")
    if policy.get("same_family_counts_as_independent_reasoning") is not False:
        errors.append("same_family_counts_as_independent_reasoning must be false")
    if policy.get("provider_voting") != "forbidden":
        errors.append("provider_voting must be forbidden")

    max_parallel = policy.get("max_parallel") or {}
    for profile in REQUIRED_PROFILES:
        value = max_parallel.get(profile)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"max_parallel.{profile} must be a non-negative integer")
    if max_parallel.get("FAST") != 0:
        errors.append("max_parallel.FAST must be 0 (FAST may not use external workers)")

    selection = policy.get("selection") or {}
    filters = selection.get("filter_before_score") or []
    if not isinstance(filters, list) or not filters:
        errors.append("selection.filter_before_score must be a non-empty list")

    privacy = policy.get("privacy") or {}
    if privacy.get("SECRET") != "deny_external_free":
        errors.append("privacy.SECRET must be deny_external_free")

    quota = policy.get("quota") or {}

    if not capabilities_path.is_absolute():
        capabilities_path = root / capabilities_path
    capabilities_doc = yaml.safe_load(capabilities_path.read_text(encoding="utf-8")) or {}
    if capabilities_doc.get("policy", {}).get("routing_authority") is not False:
        errors.append("domain_capabilities routing_authority must be false")
    if capabilities_doc.get("policy", {}).get("weights_are_selection_metadata_only") is not True:
        errors.append("domain_capabilities must remain selection metadata, not a routing authority")
    domain_weights = {
        str(name): {str(dim): float(weight) for dim, weight in (row.get("capabilities") or {}).items()}
        for name, row in (capabilities_doc.get("domains") or {}).items()
    }
    if not domain_weights:
        errors.append("domain_capabilities declares no domains")
    scoring = capabilities_doc.get("scoring") or {}

    evidence = capabilities_doc.get("capability_evidence") or {}
    if evidence.get("routing_authority") is not False:
        errors.append("capability_evidence routing_authority must be false")
    freshness = evidence.get("default_freshness_hours")
    hard_gate = evidence.get("hard_gate") or {}
    min_verified = hard_gate.get("min_verified_candidates")
    min_ratio = hard_gate.get("min_coverage_ratio")
    default_enabled = hard_gate.get("default_enabled")
    overrides = hard_gate.get("overrides") or {}
    if not isinstance(freshness, int) or isinstance(freshness, bool) or not 1 <= freshness <= 8760:
        errors.append("capability_evidence.default_freshness_hours must be an integer in 1..8760")
    if not isinstance(min_verified, int) or isinstance(min_verified, bool) or min_verified < 1:
        errors.append("capability_evidence.hard_gate.min_verified_candidates must be an integer >= 1")
    if isinstance(min_ratio, bool) or not isinstance(min_ratio, (int, float)) or not 0.0 <= float(min_ratio) <= 1.0:
        errors.append("capability_evidence.hard_gate.min_coverage_ratio must be between 0 and 1")
    if default_enabled is not False:
        errors.append("capability_evidence.hard_gate.default_enabled must remain false in Phase A")
    if not isinstance(overrides, dict) or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in overrides.items()):
        errors.append("capability_evidence.hard_gate.overrides must map string keys to booleans")

    if errors:
        raise SystemExit("MODEL_MESH_POLICY_COMPILE=FAIL " + "; ".join(errors))

    contract = {
        "schema_version": 1,
        "mode": policy["mode"],
        "routing_authority": False,
        "reasoning_authority": False,
        "max_parallel": {profile: int(max_parallel[profile]) for profile in REQUIRED_PROFILES},
        "selection_filters": [str(entry) for entry in filters],
        "free_status_unknown_action": str(policy.get("free_status_unknown_action", "exclude")),
        "paid_fallback": policy["paid_fallback"],
        "provider_voting": policy["provider_voting"],
        "same_family_counts_as_independent_reasoning": False,
        "privacy": {key: str(value) for key, value in sorted(privacy.items())},
        "quota": {
            "respect_provider_reset": bool(quota.get("respect_provider_reset", False)),
            "use_runtime_headers_first": bool(quota.get("use_runtime_headers_first", False)),
            "cooldown_on_exhaustion": bool(quota.get("cooldown_on_exhaustion", False)),
        },
        "domain_capabilities": domain_weights,
        "capability_evidence": {
            "routing_authority": False,
            "default_freshness_hours": int(freshness),
            "hard_gate": {
                "default_enabled": False,
                "min_verified_candidates": int(min_verified),
                "min_coverage_ratio": float(min_ratio),
                "overrides": {str(key): bool(value) for key, value in sorted(overrides.items())},
            },
        },
        "scoring": {
            "capability_fit": float(scoring.get("capability_fit", 0.5)),
            "measured_quality": float(scoring.get("measured_quality", 0.25)),
        },
    }

    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile the canonical Model Mesh policy into a runtime contract")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--domain-capabilities", default=DEFAULT_DOMAIN_CAPABILITIES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    contract = compile_policy(Path(args.root).resolve(), policy_path=Path(args.policy), capabilities_path=Path(args.domain_capabilities), output=Path(args.output))
    print(
        "MODEL_MESH_POLICY_COMPILE=PASS "
        f"max_parallel={json.dumps(contract['max_parallel'], sort_keys=True)} "
        f"filters={len(contract['selection_filters'])} "
        f"domains={len(contract['domain_capabilities'])} "
        f"capability_evidence_freshness={contract['capability_evidence']['default_freshness_hours']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
