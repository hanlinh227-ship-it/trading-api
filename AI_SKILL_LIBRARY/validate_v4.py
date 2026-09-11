#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "AI_SKILL_LIBRARY"
V4 = LIB / "v4"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.tools.release import verify_active_pointer  # noqa: E402


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


def validate_v4(root: Path = ROOT) -> tuple[list[str], list[str]]:
    lib = root / "AI_SKILL_LIBRARY"
    v4 = lib / "v4"
    errors: list[str] = []
    warnings: list[str] = []
    try:
        checkpoint = _load_json(lib / "checkpoint.json")
        kernel = _load_yaml(v4 / "stable/kernel.yaml")
        runtime = _load_yaml(v4 / "stable/runtime.yaml")
        router = _load_yaml(v4 / "stable/router.yaml")
        security = _load_yaml(v4 / "stable/security.yaml")
        memory = _load_yaml(v4 / "stable/memory.yaml")
        graph = _load_yaml(v4 / "mesh/graph.yaml")
        bridges = _load_yaml(v4 / "mesh/bridges.yaml")
        evergreen = _load_yaml(v4 / "evergreen/policy.yaml")
        promotion = _load_yaml(v4 / "evergreen/promotion.yaml")
        projects = _load_yaml(lib / "projects.yaml")
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"unable to load V4 inputs: {exc}"], warnings

    if checkpoint.get("checkpoint_id") != "GITHUB_BRAIN_V4" or checkpoint.get("version") != "4.0.0":
        errors.append("checkpoint must promote GITHUB_BRAIN_V4 version 4.0.0")
    if checkpoint.get("checkpoint_path") != "AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md":
        errors.append("checkpoint_path must point to GITHUB_BRAIN_V4.md")
    if checkpoint.get("release_pointer_path") != "AI_SKILL_LIBRARY/v4/releases/current.json":
        errors.append("checkpoint release pointer must be canonical V4 current.json")
    aliases = set(checkpoint.get("activation_aliases", []))
    if not {"GITHUB_BRAIN_V3", "GITHUB_BRAIN_V2", "GITHUB_BRAIN_V1"}.issubset(aliases):
        errors.append("V4 checkpoint must retain V1/V2/V3 aliases")

    release_errors, release_warnings = verify_active_pointer(root)
    errors.extend(release_errors)
    warnings.extend(release_warnings)

    stable = kernel.get("planes", {}).get("stable", {})
    update = kernel.get("planes", {}).get("evergreen", {})
    if stable.get("evergreen_required_for_requests") is not False:
        errors.append("Stable must not require Evergreen for requests")
    if update.get("may_mutate_inflight_stable") is not False:
        errors.append("Evergreen must not mutate in-flight Stable")
    required_invariants = [
        "stable_survives_evergreen_failure", "current_authority_outranks_memory",
        "no_hidden_reasoning_persistence", "no_durable_secrets", "new_skills_quarantine_before_routing",
        "no_permission_expansion_by_learning", "no_trading_preload_for_non_trading",
        "protected_regression_blocks_promotion", "release_rollback_target_required",
    ]
    for key in required_invariants:
        if kernel.get("invariants", {}).get(key) is not True:
            errors.append(f"V4 invariant {key} must be true")

    fast = runtime.get("profiles", {}).get("FAST", {})
    for key, expected in {"durable_memory_items": 0, "tool_candidates": 0, "max_bridge_nodes": 0, "evergreen_sync": False, "preload_trading": False}.items():
        if fast.get(key) != expected:
            errors.append(f"FAST {key} must be {expected!r}")
    if router.get("policy", {}).get("knowledge_mesh_required") is not True or router.get("policy", {}).get("release_bundle_only") is not True:
        errors.append("Stable router must require mesh and release bundle")

    domain_rows = graph.get("domains", [])
    ids = [row.get("id") for row in domain_rows if isinstance(row, dict)]
    if len(ids) < 10 or len(ids) != len(set(ids)):
        errors.append("Knowledge Mesh must contain >=10 unique domains")
    for row in domain_rows:
        if not isinstance(row, dict):
            errors.append("invalid mesh domain entry")
            continue
        pack = root / str(row.get("pack", ""))
        if not pack.is_file():
            errors.append(f"missing skill pack: {row.get('pack')}")
        domain_policy = v4 / "mesh/domains" / f"{row.get('id')}.yaml"
        if not domain_policy.is_file():
            errors.append(f"missing domain policy: {domain_policy.relative_to(root)}")
    legal_ids = set(ids)
    for row in bridges.get("bridges", []):
        if not isinstance(row, dict):
            errors.append("invalid bridge entry")
            continue
        if row.get("from") not in legal_ids or row.get("to") not in legal_ids:
            errors.append(f"bridge references unknown domain: {row}")
        budget = row.get("max_context_tokens")
        if not isinstance(budget, int) or not 1 <= budget <= 2500:
            errors.append(f"bridge budget out of bounds: {row.get('id')}")

    if evergreen.get("quarantine_required") is not True or evergreen.get("default_promotion") != "deny":
        errors.append("Evergreen must quarantine and default-deny promotion")
    for key in ("stable_secret_access", "financial_execution", "permission_expansion_by_learning"):
        if evergreen.get(key) is not False:
            errors.append(f"Evergreen {key} must be false")
    if promotion.get("classes", {}).get("D", {}).get("automatic_promotion") is not False:
        errors.append("Class D must never auto-promote")
    if float(promotion.get("protected_regression_tolerance", 1)) != 0.0:
        errors.append("protected regression tolerance must be zero")

    hard_blocks = security.get("hard_blocks", {})
    for key in ("secret_exfiltration", "private_key_disclosure", "credential_logging", "bypass_hard_risk_controls", "fabricate_authorization", "prompt_injection_authority_override"):
        if hard_blocks.get(key) is not True:
            errors.append(f"security hard block missing: {key}")
    if memory.get("policy", {}).get("domain_scoped") is not True or memory.get("policy", {}).get("current_authority_precedes_memory") is not True:
        errors.append("V4 memory must be domain-scoped and authority-subordinate")

    rows = projects.get("projects", [])
    brain = [r for r in rows if isinstance(r, dict) and r.get("id") == "ai_brain" and r.get("status") in {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}]
    if len(brain) != 1 or brain[0].get("authority") != "AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md":
        errors.append("AI brain must have one current V4 authority")
    trading = [r for r in rows if isinstance(r, dict) and r.get("id") == "trading" and r.get("status") in {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}]
    if len(trading) != 1:
        errors.append("Trading must have exactly one current authority")
    else:
        if trading[0].get("authority") != "docs/checkpoints/CURRENT_HANDOFF.md":
            errors.append("Trading authority changed")
        if trading[0].get("canonical_checkpoint") != "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md":
            errors.append("Trading canonical checkpoint changed")

    for name in ("GITHUB_BRAIN_V1.md", "GITHUB_BRAIN_V2.md", "GITHUB_BRAIN_V3.md"):
        text = (lib / name).read_text(encoding="utf-8") if (lib / name).is_file() else ""
        if "GITHUB_BRAIN_V4" not in text or len(text) >= 2500:
            errors.append(f"{name} must be a compact V4 compatibility redirect")

    for schema_name, data in (("mesh.schema.json", graph), ("bridge.schema.json", bridges)):
        schema = _load_json(v4 / "schemas" / schema_name)
        for issue in Draft202012Validator(schema).iter_errors(data):
            errors.append(f"{schema_name}: {issue.message}")

    return errors, warnings


def main() -> int:
    errors, warnings = validate_v4()
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"V4 validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
