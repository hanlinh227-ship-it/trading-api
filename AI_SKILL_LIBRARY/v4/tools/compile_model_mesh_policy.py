"""Compile the canonical Model Mesh policy into a runtime contract.

`AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml` is the checkpoint-declared
authority for parallelism and selection, but until now it was not compiled
into anything: the same limits were hard-coded independently in
`cloudflare-worker/model-mesh/contracts.js`, in the `/brain/mesh/health`
response and in the deploy workflow's assertions. Editing the canonical policy
therefore changed nothing at runtime, silently.

This compiler makes the canonical policy the single source of truth:

    policy.yaml -> compiler -> generated contract -> runtime/planner -> CI
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
    # FAST must never fan out to an external worker; this is the contract the
    # whole Brain-authority model rests on, so it is enforced at compile time.
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

    # domain_capabilities.yaml declares weights_are_selection_metadata_only, so
    # it is compiled in as RANKING authority: it decides which capability
    # dimensions matter for a routed domain and how much. It is not a hard gate
    # -- the active registry does not yet declare every dimension for every
    # model, and treating a missing declaration as disqualifying would zero out
    # whole domains (no admitted model currently declares math_quant or
    # data_analysis, which the trading domain weights most heavily).
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
        f"domains={len(contract['domain_capabilities'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
