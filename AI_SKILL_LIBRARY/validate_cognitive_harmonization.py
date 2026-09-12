#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "AI_SKILL_LIBRARY"
POLICY_PATH = LIB / "v4/stable/cognitive_harmonization.yaml"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping: {path}")
    return data


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def validate_cognitive_harmonization(root: Path = ROOT) -> tuple[list[str], list[str]]:
    lib = root / "AI_SKILL_LIBRARY"
    errors: list[str] = []
    warnings: list[str] = []

    try:
        checkpoint = _load_json(lib / "checkpoint.json")
        policy = _load_yaml(lib / "v4/stable/cognitive_harmonization.yaml")
        runtime = _load_yaml(lib / "v4/stable/runtime.yaml")
        kernel = _load_yaml(lib / "v4/stable/kernel.yaml")
        projects = _load_yaml(lib / "projects.yaml")
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"unable to load cognitive harmonization inputs: {exc}"], warnings

    expected_path = "AI_SKILL_LIBRARY/v4/stable/cognitive_harmonization.yaml"
    if checkpoint.get("cognitive_harmonization_path") != expected_path:
        errors.append("checkpoint must discover the canonical cognitive harmonization policy")
    if kernel.get("cognitive_harmonization") != expected_path:
        errors.append("kernel must point to the canonical cognitive harmonization policy")
    if runtime.get("harmonization", {}).get("policy") != expected_path:
        errors.append("runtime must point to the canonical cognitive harmonization policy")

    authority = policy.get("authority", {})
    if authority.get("external_framework_is_reasoning_authority") is not False:
        errors.append("external frameworks must not become reasoning authority")
    if authority.get("provider_consensus_is_authorization") is not False:
        errors.append("provider consensus must not become authorization")
    if authority.get("current_project_authority_precedes_external_methods") is not True:
        errors.append("current project authority must precede external methods")
    if authority.get("stable_security_precedes_external_methods") is not True:
        errors.append("Stable security must precede external methods")

    harmonization = policy.get("harmonization", {})
    if harmonization.get("majority_vote_for_truth") is not False:
        errors.append("harmonization must forbid majority vote for truth")
    if harmonization.get("silent_averaging_of_conflicts") is not False:
        errors.append("harmonization must forbid silent averaging of conflicts")
    if harmonization.get("unresolved_material_conflict") != "disclose_and_block_high_consequence_dependent_conclusion":
        errors.append("unresolved material conflicts must fail closed for high-consequence conclusions")

    loop = policy.get("agent_loop", {})
    if loop.get("enabled") is not True:
        errors.append("bounded agent loop must be enabled")
    max_iterations = loop.get("max_iterations")
    if not isinstance(max_iterations, int) or not 1 <= max_iterations <= 3:
        errors.append("agent loop max_iterations must be between 1 and 3")
    for key in ("may_expand_permissions", "may_bypass_security_or_authority", "financial_execution_allowed", "hidden_reasoning_persistence"):
        if loop.get(key) is not False:
            errors.append(f"agent loop {key} must be false")

    profiles = policy.get("profiles", {})
    if profiles.get("FAST", {}).get("mode") != "disabled":
        errors.append("FAST cognitive harmonization must remain disabled")
    if profiles.get("DEEP", {}).get("mode") != "maker_checker_with_independent_grader":
        errors.append("DEEP must use maker/checker with independent grader")
    if policy.get("grader", {}).get("majority_vote_for_truth") is not False:
        errors.append("grader must not majority-vote truth")

    pyramid = policy.get("artifact_pyramid", {})
    if pyramid.get("layers") != ["summary", "analysis", "evidence_dossier"]:
        errors.append("artifact pyramid must preserve summary/analysis/evidence_dossier layers")
    if pyramid.get("may_override_verification") is not False or pyramid.get("may_override_authority") is not False:
        errors.append("artifact shaping must not override verification or authority")

    learning = policy.get("learning", {})
    for key in ("direct_stable_self_patch", "permission_expansion_by_learning", "secrets_or_sensitive_payloads_may_be_distilled"):
        if learning.get(key) is not False:
            errors.append(f"learning {key} must be false")
    if learning.get("candidate_has_zero_routing_authority_until_promoted") is not True:
        errors.append("learning candidates must have zero routing authority until promoted")

    fast_stages = runtime.get("profiles", {}).get("FAST", {}).get("stages", [])
    forbidden_fast = {"maker_checker", "independent_grader", "harmonize", "artifact_shape"}
    if forbidden_fast.intersection(fast_stages):
        errors.append("FAST stages must not include cognitive harmonization stages")
    deep_stages = runtime.get("profiles", {}).get("DEEP", {}).get("stages", [])
    for stage in ("maker_checker", "independent_grader", "harmonize", "verify"):
        if stage not in deep_stages:
            errors.append(f"DEEP stages must include {stage}")

    trading = [
        row for row in projects.get("projects", [])
        if isinstance(row, dict) and row.get("id") == "trading" and row.get("status") in {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}
    ]
    if len(trading) != 1 or trading[0].get("authority") != "docs/checkpoints/CURRENT_HANDOFF.md":
        errors.append("cognitive harmonization must not change Trading authority")

    invariants = kernel.get("invariants", {})
    for key in (
        "external_methods_are_reference_not_authority",
        "cognitive_loops_are_bounded",
        "harmonization_cannot_expand_permissions",
        "fast_harmonization_disabled",
    ):
        if invariants.get(key) is not True:
            errors.append(f"kernel harmonization invariant {key} must be true")

    return errors, warnings


def main() -> int:
    errors, warnings = validate_cognitive_harmonization()
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Cognitive harmonization validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
