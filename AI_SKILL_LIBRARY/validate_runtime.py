#!/usr/bin/env python3
"""Validate adaptive runtime contracts for GITHUB_BRAIN V2/V3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "schemas" / "runtime.schema.json"
FILES = {
    "bootstrap": HERE / "bootstrap.yaml",
    "runtime": HERE / "runtime.yaml",
    "memory": HERE / "memory.yaml",
    "evals": HERE / "evals.yaml",
    "observability": HERE / "observability.yaml",
    "security": HERE / "security.yaml",
}

REQUIRED_MEMORY_METADATA = {"source", "confidence", "created_at", "last_verified", "superseded_by", "scope"}
REQUIRED_MEMORY_EXCLUSIONS = {"secrets", "credentials", "private_keys", "account_data", "sensitive_personal_data", "raw_private_chat"}
REQUIRED_EVAL_GATES = {"tests", "eval_baseline", "security", "authority", "ci"}
HIGH_IMPACT_CLASSES = {"destructive", "financial", "credential_sensitive"}
BUDGET_FIELDS = ("context_tokens", "memory_items", "tool_candidates", "replan_budget")


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _protocol_ok(checkpoint_id: object, version: object) -> bool:
    if not isinstance(version, str):
        return False
    try:
        major, minor, patch = (int(part) for part in version.split("."))
    except (TypeError, ValueError):
        return False
    if checkpoint_id == "GITHUB_BRAIN_V2":
        return major == 2 and (minor, patch) >= (1, 0)
    if checkpoint_id == "GITHUB_BRAIN_V3":
        return major == 3 and (minor, patch) >= (0, 0)
    return False


def validate_runtime_data(bootstrap: dict, runtime: dict, memory: dict, evals: dict, observability: dict, security: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    checkpoint_id = bootstrap.get("checkpoint_id")
    if checkpoint_id not in {"GITHUB_BRAIN_V2", "GITHUB_BRAIN_V3"}:
        errors.append("bootstrap.checkpoint_id must be GITHUB_BRAIN_V2 or GITHUB_BRAIN_V3")
    if not _protocol_ok(checkpoint_id, bootstrap.get("protocol_version")):
        errors.append("bootstrap.protocol_version is incompatible with checkpoint_id")
    if bootstrap.get("mandatory_router") != "task_router":
        errors.append("bootstrap.mandatory_router must be task_router")
    if bootstrap.get("default_profile") != "FAST":
        errors.append("bootstrap.default_profile must be FAST")
    paths = _mapping(bootstrap.get("paths"))
    required_paths = {"brain", "core_protocol", "router", "runtime", "projects", "skills", "sources", "plugins", "memory", "evals", "observability", "security"}
    if checkpoint_id == "GITHUB_BRAIN_V3":
        required_paths |= {"kernel", "context", "reliability", "evidence", "orchestration", "migration"}
    for key in sorted(required_paths - set(paths)):
        errors.append(f"bootstrap missing required path {key!r}")
    lazy = _mapping(bootstrap.get("lazy_load"))
    for key in ("full_skill_catalog", "project_state", "trading_state"):
        if lazy.get(key) is not True:
            errors.append(f"bootstrap.lazy_load.{key} must be true")

    order = _list(runtime.get("profile_order"))
    if order != ["FAST", "STANDARD", "DEEP"]:
        errors.append("runtime.profile_order must be FAST, STANDARD, DEEP")
    profiles = _mapping(runtime.get("profiles"))
    for name in ("FAST", "STANDARD", "DEEP"):
        if name not in profiles:
            errors.append(f"runtime missing profile {name}")
    controls = _mapping(runtime.get("controls"))
    maxima = {
        "context_tokens": int(controls.get("max_context_tokens", 99999)),
        "memory_items": int(controls.get("max_memory_items", 99)),
        "tool_candidates": int(controls.get("max_tool_candidates", 99)),
        "replan_budget": int(controls.get("max_replan_budget", 99)),
    }
    for name in ("FAST", "STANDARD", "DEEP"):
        row = _mapping(profiles.get(name))
        for field in BUDGET_FIELDS:
            value = row.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"profile[{name}].{field} must be a non-negative integer")
                continue
            if value > maxima[field]:
                errors.append(f"profile[{name}].{field} exceeds bounded maximum {maxima[field]}")
        supporting = row.get("max_supporting_skills")
        if not isinstance(supporting, int) or isinstance(supporting, bool) or not 0 <= supporting <= 2:
            errors.append(f"profile[{name}].max_supporting_skills must be between 0 and 2")
        if not isinstance(row.get("stages"), list):
            errors.append(f"profile[{name}].stages must be a list")

    if all(name in profiles for name in ("FAST", "STANDARD", "DEEP")):
        for field in BUDGET_FIELDS:
            values = [_mapping(profiles[name]).get(field) for name in ("FAST", "STANDARD", "DEEP")]
            if all(isinstance(value, int) and not isinstance(value, bool) for value in values) and not (values[0] <= values[1] <= values[2]):
                errors.append(f"runtime profile budget {field} must be monotonic FAST <= STANDARD <= DEEP")

    fast = _mapping(profiles.get("FAST"))
    for field in ("memory_items", "tool_candidates", "replan_budget", "max_supporting_skills"):
        if fast.get(field) != 0:
            errors.append(f"FAST {field} must be 0")
    fast_stages = set(_list(fast.get("stages")))
    for forbidden in ("project_authority", "bounded_memory", "scoped_memory", "relevant_plugins", "planner", "critic", "eval", "trace", "task_graph"):
        if forbidden in fast_stages:
            errors.append(f"FAST stages must not include {forbidden}")
    for required in ("task_router", "answer"):
        if required not in fast_stages:
            errors.append(f"FAST stages must include {required}")

    if controls.get("one_profile_per_request") is not True:
        errors.append("runtime.controls.one_profile_per_request must be true")
    if controls.get("control_plane_does_not_consume_supporting_skill_budget") is not True:
        errors.append("runtime control plane must not consume supporting-skill budget")
    if controls.get("full_skill_catalog_injection") is not False:
        errors.append("runtime.controls.full_skill_catalog_injection must be false")

    layers = _mapping(memory.get("layers"))
    if set(layers) != {"working", "episodic", "semantic", "procedural"}:
        errors.append("memory layers must be exactly working, episodic, semantic, procedural")
    for name, row_raw in layers.items():
        row = _mapping(row_raw)
        for field in ("max_items", "max_item_tokens"):
            value = row.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"memory layer {name}.{field} must be a positive integer")
    metadata = set(_list(memory.get("required_metadata")))
    for key in sorted(REQUIRED_MEMORY_METADATA - metadata):
        errors.append(f"memory required_metadata missing {key}")
    exclusions = set(_list(_mapping(memory.get("privacy")).get("durable_exclusions")))
    for key in sorted(REQUIRED_MEMORY_EXCLUSIONS - exclusions):
        errors.append(f"memory durable_exclusions missing {key}")
    memory_policy = _mapping(memory.get("policy"))
    if memory_policy.get("retrieve_before_write") is not True:
        errors.append("memory.policy.retrieve_before_write must be true")
    if memory_policy.get("prefer_verified_current_over_old") is not True:
        errors.append("memory.policy.prefer_verified_current_over_old must be true")
    if _mapping(_mapping(memory.get("retrieval")).get("FAST")).get("max_items") != 0:
        errors.append("memory FAST retrieval max_items must be 0")

    taxonomy = set(_list(evals.get("failure_taxonomy")))
    for key in ("user_correction", "wrong_route", "stale_context"):
        if key not in taxonomy:
            errors.append(f"eval failure_taxonomy missing {key}")
    if _mapping(evals.get("learning_loop")).get("verified_failure_to_candidate_eval") is not True:
        errors.append("eval learning loop must convert verified failures to candidate evals")
    promotion = _mapping(evals.get("promotion"))
    gates = set(_list(promotion.get("required_gates")))
    for gate in sorted(REQUIRED_EVAL_GATES - gates):
        errors.append(f"eval promotion missing required gate {gate}")
    if promotion.get("automatic_merge") is not False:
        errors.append("eval promotion automatic_merge must be false")

    obs_policy = _mapping(observability.get("policy"))
    if obs_policy.get("persist_hidden_chain_of_thought") is not False:
        errors.append("observability must not persist hidden chain-of-thought")
    allowed_events = set(_list(observability.get("allowed_events")))
    if "chain_of_thought" in allowed_events:
        errors.append("observability allowed_events must not include chain_of_thought")
    if "decision_summary" not in allowed_events:
        errors.append("observability allowed_events must include decision_summary")
    if _mapping(_mapping(observability.get("profiles")).get("FAST")).get("persistence") != "none":
        errors.append("observability FAST persistence must be none")

    classes = _mapping(security.get("risk_classes"))
    if _mapping(classes.get("read_only")).get("default") != "allow":
        errors.append("security read_only default must be allow")
    for name in HIGH_IMPACT_CLASSES:
        if _mapping(classes.get(name)).get("default") in (None, "allow"):
            errors.append(f"security {name} default must not be allow")
    hard_blocks = _mapping(security.get("hard_blocks"))
    for key in ("secret_exfiltration", "private_key_disclosure"):
        if hard_blocks.get(key) is not True:
            errors.append(f"security hard block {key} must be true")

    return errors, warnings


def main() -> int:
    try:
        data = {name: yaml.safe_load(path.read_text(encoding="utf-8")) for name, path in FILES.items()}
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"[ERROR] unable to load adaptive runtime inputs: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate_runtime_data(**data)
    errors.extend(f"runtime schema: {err.message}" for err in Draft202012Validator(schema).iter_errors(data["runtime"]))
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Adaptive runtime validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
