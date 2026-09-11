#!/usr/bin/env python3
"""Validate GITHUB_BRAIN_V3 unified kernel invariants and V2.2→V3 migration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCHEMA = HERE / "schemas" / "kernel.schema.json"


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _inside(root: Path, rel: object) -> Path | None:
    if not isinstance(rel, str) or not rel.strip():
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def validate_v3_data(
    kernel: dict,
    migration: dict,
    context: dict,
    reliability: dict,
    evidence: dict,
    orchestration: dict,
    projects: dict,
    router: dict,
    checkpoint: dict,
    *,
    root: Path = ROOT,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    # Checkpoint / migration authority.
    if checkpoint.get("checkpoint_id") != "GITHUB_BRAIN_V3":
        errors.append("checkpoint_id must be GITHUB_BRAIN_V3")
    if checkpoint.get("version") != "3.0.0":
        errors.append("checkpoint version must be 3.0.0")
    if checkpoint.get("checkpoint_path") != "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md":
        errors.append("checkpoint_path must point to GITHUB_BRAIN_V3.md")
    if checkpoint.get("kernel_path") != "AI_SKILL_LIBRARY/kernel.yaml":
        errors.append("kernel_path must point to AI_SKILL_LIBRARY/kernel.yaml")
    aliases = set(_list(checkpoint.get("activation_aliases")))
    if not {"GITHUB_BRAIN_V2", "GITHUB_BRAIN_V1"}.issubset(aliases):
        errors.append("checkpoint must keep GITHUB_BRAIN_V2 and GITHUB_BRAIN_V1 compatibility aliases")

    expected_versions = ["2.1.0", "2.2.0", "2.3.0", "2.4.0", "3.0.0"]
    versions = [row.get("version") for row in _list(migration.get("milestones")) if isinstance(row, dict)]
    if versions != expected_versions:
        errors.append(f"migration milestones must be exactly {expected_versions!r}")
    if migration.get("current") != "3.0.0":
        errors.append("migration current must be 3.0.0")
    if migration.get("authority") != "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md":
        errors.append("migration authority must be GITHUB_BRAIN_V3.md")

    # Kernel.
    if kernel.get("version") != 3:
        errors.append("kernel.version must be 3")
    if kernel.get("authority") != "GITHUB_BRAIN_V3":
        errors.append("kernel.authority must be GITHUB_BRAIN_V3")
    if kernel.get("default_profile") != "FAST":
        errors.append("kernel.default_profile must be FAST")
    profiles = _mapping(kernel.get("profiles"))
    if set(profiles) != {"FAST", "STANDARD", "DEEP"}:
        errors.append("kernel profiles must be exactly FAST, STANDARD, DEEP")
    fast = _mapping(profiles.get("FAST"))
    if fast.get("durable_memory_items") != 0:
        errors.append("FAST durable_memory_items must be 0")
    if fast.get("tool_candidates") != 0:
        errors.append("FAST tool_candidates must be 0")
    if fast.get("replans") != 0:
        errors.append("FAST replans must be 0")
    if fast.get("orchestration") != "serial":
        errors.append("FAST orchestration must be serial")

    invariants = _mapping(kernel.get("invariants"))
    required_true = {
        "one_ai_brain_authority",
        "one_current_authority_per_project",
        "current_authority_outranks_memory",
        "current_runtime_outranks_cached_state",
        "no_hidden_reasoning_persistence",
        "no_durable_secrets",
        "no_auto_merge_self_improvement",
        "no_trading_preload_for_non_trading",
        "source_code_is_not_live_proof",
        "verification_before_completion_claim",
        "high_impact_min_profile_deep",
    }
    for key in sorted(required_true):
        if invariants.get(key) is not True:
            if key == "no_auto_merge_self_improvement":
                errors.append("V3 invariant must forbid automatic self-improvement merge")
            else:
                errors.append(f"V3 invariant {key} must be true")
    promotion = _mapping(kernel.get("promotion"))
    if promotion.get("automatic_merge") is not False:
        errors.append("V3 promotion automatic merge must be false")

    # V2.2 context scheduler.
    context_policy = _mapping(context.get("policy"))
    if context_policy.get("authority_first") is not True:
        errors.append("context must be authority-first")
    if context_policy.get("deduplicate") is not True:
        errors.append("context deduplication must be enabled")
    if context_policy.get("cache_never_outranks_fresh_authority") is not True:
        errors.append("context cache must never outrank fresh authority")
    context_profiles = _mapping(context.get("profiles"))
    if _mapping(context_profiles.get("FAST")).get("durable_memory_items") != 0:
        errors.append("context FAST durable memory items must be 0")
    cache = _mapping(context.get("cache"))
    if "checkpoint_change" not in _list(cache.get("invalidate_on")):
        errors.append("context cache must invalidate on checkpoint_change")
    if cache.get("cache_live_data") is not False:
        errors.append("context cache must not cache live data")

    # V2.3 reliability and evidence.
    retry = _mapping(reliability.get("retry"))
    attempts = retry.get("max_attempts")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= 3:
        errors.append("reliability retry max_attempts must be between 1 and 3")
    if _mapping(reliability.get("circuit_breaker")).get("enabled") is not True:
        errors.append("reliability circuit breaker must be enabled")
    fallback = _mapping(reliability.get("fallback"))
    if fallback.get("must_disclose_degraded_state") is not True:
        errors.append("reliability fallback must disclose degraded state")
    if fallback.get("never_widen_permissions") is not True:
        errors.append("reliability fallback must never widen permissions")

    ledger = _mapping(evidence.get("ledger"))
    if ledger.get("persist_hidden_reasoning") is not False:
        errors.append("evidence ledger must not persist hidden reasoning")
    conflicts = _mapping(evidence.get("conflicts"))
    if conflicts.get("prefer_current_authority") is not True:
        errors.append("evidence conflicts must prefer current authority")
    if conflicts.get("material_conflict_requires_resolution_or_disclosure") is not True:
        errors.append("material evidence conflict must be resolved or disclosed")
    if _mapping(evidence.get("uncertainty")).get("escalate_material_conflict") is not True:
        errors.append("evidence uncertainty must escalate material conflicts")

    # V2.4 orchestration.
    if _mapping(orchestration.get("task_graph")).get("enabled") is not True:
        errors.append("orchestration task graph must be enabled")
    parallel = _mapping(orchestration.get("parallelism"))
    max_parallel = parallel.get("max_parallel_tasks")
    if not isinstance(max_parallel, int) or isinstance(max_parallel, bool) or not 1 <= max_parallel <= 4:
        errors.append("orchestration parallel max_parallel_tasks must be between 1 and 4")
    if parallel.get("dependency_aware") is not True:
        errors.append("orchestration parallelism must be dependency-aware")
    if parallel.get("serial_fallback") is not True:
        errors.append("orchestration parallelism must have serial fallback")
    if _mapping(orchestration.get("safety")).get("parallel_high_impact_writes") is not False:
        errors.append("orchestration must not parallelize high-impact writes")

    # Single current AI brain authority in router and project registry.
    router_auth = [row for row in _list(router.get("authorities")) if isinstance(row, dict) and row.get("scope") == "ai_brain" and row.get("status") == "CURRENT_AUTHORITY"]
    if len(router_auth) != 1 or router_auth[0].get("path") != "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md":
        errors.append("ai_brain authority must be exactly one CURRENT_AUTHORITY pointing to GITHUB_BRAIN_V3.md")

    project_rows = _list(projects.get("projects"))
    ai_rows = [row for row in project_rows if isinstance(row, dict) and row.get("id") == "ai_brain" and row.get("status") in {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}]
    if len(ai_rows) != 1 or ai_rows[0].get("authority") != "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md":
        errors.append("project ai_brain authority must be exactly one current GITHUB_BRAIN_V3.md")

    trading_rows = [row for row in project_rows if isinstance(row, dict) and row.get("id") == "trading" and row.get("status") in {"CURRENT", "ACTIVE", "CURRENT_AUTHORITY"}]
    if len(trading_rows) != 1:
        errors.append("trading must have exactly one current authority")
    else:
        trading = trading_rows[0]
        if trading.get("authority") != "docs/checkpoints/CURRENT_HANDOFF.md":
            errors.append("trading authority must remain docs/checkpoints/CURRENT_HANDOFF.md")
        if trading.get("canonical_checkpoint") != "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md":
            errors.append("trading canonical checkpoint must remain BYBIT_BTC_STATEFLOW_2_1_20260904.md")

    # Files referenced by V3 must stay inside repository and exist when validating a real tree.
    for key in (
        "bootstrap_path", "checkpoint_path", "kernel_path", "router_path", "runtime_path",
        "context_path", "reliability_path", "evidence_path", "orchestration_path", "projects_path",
        "skill_catalog_path", "memory_path", "evals_path", "observability_path", "security_path",
        "plugins_path", "registry_path", "migration_path", "v3_validator_path",
    ):
        path = _inside(root, checkpoint.get(key))
        if path is None or not path.is_file():
            errors.append(f"V3 checkpoint reference missing for {key}: {checkpoint.get(key)!r}")

    return errors, warnings


def main() -> int:
    try:
        names = ["kernel", "migration", "context", "reliability", "evidence", "orchestration", "projects", "router"]
        data = {name: yaml.safe_load((HERE / f"{name}.yaml").read_text(encoding="utf-8")) for name in names}
        data["checkpoint"] = json.loads((HERE / "checkpoint.json").read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"[ERROR] unable to load V3 inputs: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate_v3_data(**data)
    errors.extend(f"kernel schema: {err.message}" for err in Draft202012Validator(schema).iter_errors(data["kernel"]))
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"V3 validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
