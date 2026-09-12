#!/usr/bin/env python3
"""Validate lazy skill routing, references, cycles, conflicts and schema contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROUTER_PATH = HERE / "router.yaml"
CATALOG_PATH = HERE / "skills" / "catalog.yaml"
PLUGINS_PATH = HERE / "plugins.yaml"
SOURCES_PATH = HERE / "sources.yaml"
STABLE_ROUTER_PATH = HERE / "v4" / "stable" / "router.yaml"
STABLE_RUNTIME_PATH = HERE / "v4" / "stable" / "runtime.yaml"
SCHEMAS = HERE / "schemas"
REQUIRED_METADATA = {
    "id", "domain", "triggers", "excludes", "requires", "conflicts_with",
    "priority", "tools", "sources", "output_contract",
}
ALLOWED_USAGE_TIERS = {"TRAINING_OK", "RAG_ONLY", "REFERENCE_ONLY", "MANUAL_REVIEW"}


def _cycles(graph: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}
    stack: list[str] = []
    found: list[str] = []

    def visit(node: str) -> None:
        marker = state.get(node, 0)
        if marker == 1:
            if node in stack:
                start = stack.index(node)
                found.append(" -> ".join(stack[start:] + [node]))
            return
        if marker == 2:
            return
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt in graph:
                visit(nxt)
        stack.pop()
        state[node] = 2

    for node in graph:
        visit(node)
    return sorted(set(found))


def validate_router_data(router: dict, catalog: dict, plugins: dict, sources: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    defaults = router.get("defaults", {}) if isinstance(router, dict) else {}
    if router.get("version") != 2:
        errors.append("router.version must be 2")
    if defaults.get("route_every_request") is not True:
        errors.append("router must route every request")
    if defaults.get("mandatory_skill") != "task_router":
        errors.append("router.defaults.mandatory_skill must be task_router")
    if defaults.get("max_supporting_skills") != 2:
        errors.append("router.defaults.max_supporting_skills must be 2")
    if defaults.get("preload_all_skills") is not False:
        errors.append("router must not preload all skills")
    if defaults.get("preload_trading_state") is not False:
        errors.append("router must not preload trading state")

    plugin_caps = {
        row.get("capability") for row in plugins.get("plugins", [])
        if isinstance(row, dict) and isinstance(row.get("capability"), str)
    }
    source_categories = {
        row.get("category") for row in sources.get("sources", [])
        if isinstance(row, dict) and isinstance(row.get("category"), str)
    }

    rows = catalog.get("skills", []) if isinstance(catalog, dict) else []
    by_id: dict[str, dict] = {}
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"skill[{idx}] must be a mapping")
            continue
        sid = row.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"skill[{idx}] id must be non-empty")
            continue
        if sid in by_id:
            errors.append(f"duplicate skill id {sid!r}")
            continue
        by_id[sid] = row
        missing = REQUIRED_METADATA - set(row)
        if missing:
            errors.append(f"skill[{sid}] missing metadata: {sorted(missing)!r}")
        for field in ("triggers", "excludes", "requires", "conflicts_with", "tools", "sources"):
            if not isinstance(row.get(field), list):
                errors.append(f"skill[{sid}] {field} must be a list")
        if not isinstance(row.get("priority"), int):
            errors.append(f"skill[{sid}] priority must be an integer")
        if not isinstance(row.get("output_contract"), str) or not row.get("output_contract", "").strip():
            errors.append(f"skill[{sid}] output_contract must be non-empty")
        for tool in row.get("tools", []):
            if tool not in plugin_caps:
                errors.append(f"skill[{sid}] unknown tool {tool!r}")
        for source in row.get("sources", []):
            if source not in source_categories:
                errors.append(f"skill[{sid}] unknown source category {source!r}")

    if "task_router" not in by_id:
        errors.append("task_router skill is missing")

    graph: dict[str, list[str]] = {}
    for sid, row in by_id.items():
        requires = row.get("requires", []) if isinstance(row.get("requires"), list) else []
        conflicts = row.get("conflicts_with", []) if isinstance(row.get("conflicts_with"), list) else []
        graph[sid] = list(requires)
        for ref in requires:
            if ref not in by_id:
                errors.append(f"skill[{sid}] requires unknown skill {ref!r}")
            if ref == sid:
                errors.append(f"skill[{sid}] cannot require itself")
        for ref in conflicts:
            if ref not in by_id:
                errors.append(f"skill[{sid}] conflicts_with unknown skill {ref!r}")
            if ref == sid:
                errors.append(f"skill[{sid}] cannot conflict with itself")
        impossible = set(requires) & set(conflicts)
        if impossible:
            errors.append(f"skill[{sid}] has impossible require/conflict overlap: {sorted(impossible)!r}")
    for cycle in _cycles(graph):
        errors.append(f"require cycle detected: {cycle}")

    legacy_rows = router.get("skills", []) if isinstance(router, dict) else []
    for row in legacy_rows:
        if isinstance(row, dict) and row.get("id") not in by_id:
            errors.append(f"router skill adapter references unknown catalog skill {row.get('id')!r}")

    max_supporting = defaults.get("max_supporting_skills", 2)
    for route in router.get("routes", []):
        if not isinstance(route, dict):
            errors.append("route must be a mapping")
            continue
        rid = route.get("id", "<unknown>")
        primary = route.get("primary")
        supporting = route.get("supporting", [])
        if primary is not None and primary not in by_id:
            errors.append(f"route[{rid}] references unknown primary skill {primary!r}")
        if not isinstance(supporting, list):
            errors.append(f"route[{rid}] supporting must be a list")
            continue
        if len(supporting) > max_supporting:
            errors.append(f"route[{rid}] exceeds max supporting skills ({max_supporting})")
        for sid in supporting:
            if sid not in by_id:
                errors.append(f"route[{rid}] references unknown supporting skill {sid!r}")
        selected = {sid for sid in [primary, *supporting] if sid}
        selected.add("task_router")
        for sid in list(selected & set(by_id)):
            missing = set(by_id[sid].get("requires", [])) - selected
            if missing:
                errors.append(f"route[{rid}] missing required skills for {sid!r}: {sorted(missing)!r}")
            collision = set(by_id[sid].get("conflicts_with", [])) & selected
            if collision:
                errors.append(f"route[{rid}] contains conflict for {sid!r}: {sorted(collision)!r}")

    policy = sources.get("policy", {}) if isinstance(sources, dict) else {}
    if policy.get("default_training") is not False:
        errors.append("sources.policy.default_training must be false")
    for idx, source in enumerate(sources.get("sources", []), start=1):
        if not isinstance(source, dict):
            continue
        tier = source.get("usage_tier")
        if tier not in ALLOWED_USAGE_TIERS:
            errors.append(f"source[{idx}] invalid usage_tier {tier!r}")
        if source.get("training") and tier != "TRAINING_OK":
            errors.append(f"source[{idx}] training=true requires usage_tier=TRAINING_OK")
        if tier == "MANUAL_REVIEW" and (source.get("rag") or source.get("training")):
            errors.append(f"source[{idx}] MANUAL_REVIEW must keep rag=false and training=false")

    return errors, warnings


def validate_skill_mandatory_contract(stable_router: dict, stable_runtime: dict, catalog: dict) -> list[str]:
    errors: list[str] = []
    skill_ids = {
        row.get("id") for row in catalog.get("skills", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    policy = stable_router.get("policy", {}) if isinstance(stable_router, dict) else {}
    fallback = policy.get("fallback_primary_skill")
    if policy.get("primary_skill_required") is not True:
        errors.append("V4 stable router must require a primary skill")
    if policy.get("skill_execution_capsule_required") is not True:
        errors.append("V4 stable router must require a skill execution capsule")
    if fallback != "core_reasoning":
        errors.append("V4 fallback_primary_skill must be core_reasoning")
    if fallback not in skill_ids:
        errors.append(f"V4 fallback_primary_skill references unknown skill {fallback!r}")
    profiles = stable_runtime.get("profiles", {}) if isinstance(stable_runtime, dict) else {}
    for name in ("FAST", "STANDARD", "DEEP"):
        profile = profiles.get(name, {})
        if profile.get("primary_skill_count") != 1:
            errors.append(f"V4 {name} primary_skill_count must be 1")
        if profile.get("skill_capsule_required") is not True:
            errors.append(f"V4 {name} skill_capsule_required must be true")
    if profiles.get("FAST", {}).get("max_supporting_skills") != 0:
        errors.append("V4 FAST max_supporting_skills must be 0")
    return errors


def _schema_errors(instance: object, schema_path: Path, label: str) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{label}: {err.message}" for err in validator.iter_errors(instance)]


def main() -> int:
    try:
        router = yaml.safe_load(ROUTER_PATH.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
        plugins = yaml.safe_load(PLUGINS_PATH.read_text(encoding="utf-8"))
        sources = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
        stable_router = yaml.safe_load(STABLE_ROUTER_PATH.read_text(encoding="utf-8"))
        stable_runtime = yaml.safe_load(STABLE_RUNTIME_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"[ERROR] unable to load router inputs: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate_router_data(router, catalog, plugins, sources)
    errors.extend(validate_skill_mandatory_contract(stable_router, stable_runtime, catalog))
    try:
        errors.extend(_schema_errors(router, SCHEMAS / "router.schema.json", "router schema"))
        for row in catalog.get("skills", []):
            errors.extend(_schema_errors(row, SCHEMAS / "skill.schema.json", f"skill[{row.get('id')}]") )
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"schema load error: {exc}")

    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Router validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
