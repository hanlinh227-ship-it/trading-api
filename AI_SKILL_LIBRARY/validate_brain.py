#!/usr/bin/env python3
"""Validate routed brain compatibility for GITHUB_BRAIN_V2/V3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MANIFEST_PATH = HERE / "checkpoint.json"
ROUTER_PATH = HERE / "router.yaml"
PLUGINS_PATH = HERE / "plugins.yaml"


def _inside_root(root: Path, rel: object) -> Path | None:
    if not isinstance(rel, str) or not rel.strip():
        return None
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def _version_ok(checkpoint_id: object, value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        major, minor, patch = (int(part) for part in value.split("."))
    except (TypeError, ValueError):
        return False
    if checkpoint_id == "GITHUB_BRAIN_V2":
        return major == 2 and (minor, patch) >= (1, 0)
    if checkpoint_id == "GITHUB_BRAIN_V3":
        return major == 3 and (minor, patch) >= (0, 0)
    return False


def validate_brain_data(manifest: dict, router: dict, plugins: dict, *, root: Path = REPO_ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a mapping"], warnings

    checkpoint_id = manifest.get("checkpoint_id")
    if checkpoint_id not in {"GITHUB_BRAIN_V2", "GITHUB_BRAIN_V3"}:
        errors.append("manifest.checkpoint_id must be GITHUB_BRAIN_V2 or GITHUB_BRAIN_V3")
    if not _version_ok(checkpoint_id, manifest.get("version")):
        errors.append("manifest.version is incompatible with checkpoint_id")
    aliases = manifest.get("activation_aliases", [])
    if not isinstance(aliases, list) or "GITHUB_BRAIN_V1" not in aliases:
        errors.append("manifest.activation_aliases must keep GITHUB_BRAIN_V1 compatibility")
    if checkpoint_id == "GITHUB_BRAIN_V3" and "GITHUB_BRAIN_V2" not in aliases:
        errors.append("GITHUB_BRAIN_V3 must keep GITHUB_BRAIN_V2 compatibility alias")

    common_paths = {
        "bootstrap_path": "AI_SKILL_LIBRARY/bootstrap.yaml",
        "router_path": "AI_SKILL_LIBRARY/router.yaml",
        "runtime_path": "AI_SKILL_LIBRARY/runtime.yaml",
        "plugins_path": "AI_SKILL_LIBRARY/plugins.yaml",
        "registry_path": "AI_SKILL_LIBRARY/sources.yaml",
        "projects_path": "AI_SKILL_LIBRARY/projects.yaml",
        "skill_catalog_path": "AI_SKILL_LIBRARY/skills/catalog.yaml",
        "memory_path": "AI_SKILL_LIBRARY/memory.yaml",
        "evals_path": "AI_SKILL_LIBRARY/evals.yaml",
        "observability_path": "AI_SKILL_LIBRARY/observability.yaml",
        "security_path": "AI_SKILL_LIBRARY/security.yaml",
        "validator_path": "AI_SKILL_LIBRARY/validate_brain.py",
        "router_validator_path": "AI_SKILL_LIBRARY/validate_router.py",
        "authority_validator_path": "AI_SKILL_LIBRARY/validate_authority.py",
        "runtime_validator_path": "AI_SKILL_LIBRARY/validate_runtime.py",
    }
    expected_paths = dict(common_paths)
    if checkpoint_id == "GITHUB_BRAIN_V3":
        expected_paths.update({
            "checkpoint_path": "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md",
            "kernel_path": "AI_SKILL_LIBRARY/kernel.yaml",
            "context_path": "AI_SKILL_LIBRARY/context.yaml",
            "reliability_path": "AI_SKILL_LIBRARY/reliability.yaml",
            "evidence_path": "AI_SKILL_LIBRARY/evidence.yaml",
            "orchestration_path": "AI_SKILL_LIBRARY/orchestration.yaml",
            "migration_path": "AI_SKILL_LIBRARY/migration.yaml",
            "v3_validator_path": "AI_SKILL_LIBRARY/validate_v3.py",
        })
    else:
        expected_paths["checkpoint_path"] = "AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md"

    for key, expected in expected_paths.items():
        if manifest.get(key) != expected:
            errors.append(f"manifest.{key} must be {expected!r}")
        target = _inside_root(root, expected)
        if target is None or not target.is_file():
            errors.append(f"manifest target missing: {expected}")

    if not isinstance(router, dict) or router.get("version") != 2:
        errors.append("router.version must be 2")
        return errors, warnings
    defaults = router.get("defaults") if isinstance(router.get("defaults"), dict) else {}
    max_domain = defaults.get("max_domain_skills", 3)
    if not isinstance(max_domain, int) or isinstance(max_domain, bool) or max_domain < 1:
        errors.append("router.defaults.max_domain_skills must be a positive integer")
        max_domain = 3
    if defaults.get("route_every_request") is not True:
        errors.append("router.defaults.route_every_request must be true")
    if defaults.get("mandatory_skill") != "task_router":
        errors.append("router.defaults.mandatory_skill must be task_router")
    if defaults.get("adaptive_runtime") is not True:
        errors.append("router.defaults.adaptive_runtime must be true")
    if defaults.get("default_runtime_profile") != "FAST":
        errors.append("router.defaults.default_runtime_profile must be FAST")
    if defaults.get("preload_all_skills") is not False:
        errors.append("router.defaults.preload_all_skills must be false")
    if defaults.get("preload_trading_state") is not False:
        errors.append("router.defaults.preload_trading_state must be false")

    plugin_caps: set[str] = set()
    for idx, plugin in enumerate(plugins.get("plugins", []) if isinstance(plugins, dict) else [], start=1):
        if not isinstance(plugin, dict):
            errors.append(f"plugin[{idx}] must be a mapping")
            continue
        cap = plugin.get("capability")
        if not isinstance(cap, str) or not cap:
            errors.append(f"plugin[{idx}] capability must be non-empty")
        elif cap in plugin_caps:
            errors.append(f"plugin[{idx}] duplicate capability {cap!r}")
        else:
            plugin_caps.add(cap)

    skills = router.get("skills", [])
    if not isinstance(skills, list) or not skills:
        errors.append("router.skills must be a non-empty list")
        skills = []
    ids: set[str] = set()
    skill_rows: dict[str, dict] = {}
    for idx, skill in enumerate(skills, start=1):
        if not isinstance(skill, dict):
            errors.append(f"skill[{idx}] must be a mapping")
            continue
        sid = skill.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"skill[{idx}] id must be non-empty")
            continue
        if sid in ids:
            errors.append(f"skill[{idx}] duplicate skill id {sid!r}")
        ids.add(sid)
        skill_rows[sid] = skill
        path = _inside_root(root, skill.get("path"))
        if path is None or not path.is_file():
            errors.append(f"skill[{sid}] path missing or outside repo: {skill.get('path')!r}")
        if not isinstance(skill.get("priority"), int):
            errors.append(f"skill[{sid}] priority must be an integer")
        for cap in skill.get("plugin_ids", []):
            if cap not in plugin_caps:
                errors.append(f"skill[{sid}] unknown plugin capability {cap!r}")

    for sid, skill in skill_rows.items():
        for field in ("requires", "conflicts_with"):
            refs = skill.get(field, [])
            if not isinstance(refs, list):
                errors.append(f"skill[{sid}] {field} must be a list")
                continue
            for ref in refs:
                if ref not in ids:
                    errors.append(f"skill[{sid}] {field} references unknown skill {ref!r}")
                if ref == sid:
                    errors.append(f"skill[{sid}] cannot {field} itself")

    for idx, route in enumerate(router.get("routes", []), start=1):
        if not isinstance(route, dict):
            errors.append(f"route[{idx}] must be a mapping")
            continue
        rid = route.get("id", f"#{idx}")
        supporting = route.get("supporting", [])
        if not isinstance(supporting, list):
            errors.append(f"route[{rid}] supporting must be a list")
            supporting = []
        selected = [route.get("primary"), *supporting]
        for sid in selected:
            if sid not in ids:
                errors.append(f"route[{rid}] references unknown skill {sid!r}")
        domain_selected = [sid for sid in selected if sid not in {"critical_thinking", "verification"}]
        if len(domain_selected) > max_domain:
            errors.append(f"route[{rid}] selects {len(domain_selected)} domain skills; max is {max_domain}")
        selected_set = set(selected)
        for sid in selected_set & ids:
            for required in sorted(set(skill_rows[sid].get("requires", [])) - selected_set):
                errors.append(f"route[{rid}] missing required skill {required!r} for {sid!r}")
            collision = set(skill_rows[sid].get("conflicts_with", [])) & selected_set
            if collision:
                errors.append(f"route[{rid}] contains conflicting skills {sid!r} and {sorted(collision)!r}")

    by_scope: dict[str, list[dict]] = {}
    authorities = router.get("authorities", [])
    if not isinstance(authorities, list) or not authorities:
        errors.append("router.authorities must be a non-empty list")
        authorities = []
    for idx, authority in enumerate(authorities, start=1):
        if not isinstance(authority, dict):
            errors.append(f"authority[{idx}] must be a mapping")
            continue
        scope = authority.get("scope")
        if not isinstance(scope, str) or not scope:
            errors.append(f"authority[{idx}] scope must be non-empty")
            continue
        by_scope.setdefault(scope, []).append(authority)
        path = _inside_root(root, authority.get("path"))
        if path is None or not path.is_file():
            errors.append(f"authority[{scope}] path missing or outside repo: {authority.get('path')!r}")
        follows = authority.get("follows")
        if follows:
            follow = _inside_root(root, follows)
            if follow is None or not follow.is_file():
                errors.append(f"authority[{scope}] follows missing or outside repo: {follows!r}")
    for scope, entries in by_scope.items():
        current = [entry for entry in entries if entry.get("status") == "CURRENT_AUTHORITY"]
        if len(current) > 1:
            errors.append(f"multiple current authorities for scope {scope!r}")
        elif not current:
            errors.append(f"no current authority for scope {scope!r}")

    return errors, warnings


def main() -> int:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        router = yaml.safe_load(ROUTER_PATH.read_text(encoding="utf-8"))
        plugins = yaml.safe_load(PLUGINS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"[ERROR] unable to load brain files: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate_brain_data(manifest, router, plugins)
    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Brain validation summary: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
