#!/usr/bin/env python3
"""Validate GITHUB_BRAIN_V2 checkpoint, router, plugins, skills and authorities."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MANIFEST_PATH = HERE / 'checkpoint.json'
ROUTER_PATH = HERE / 'router.yaml'
PLUGINS_PATH = HERE / 'plugins.yaml'


def _inside_root(root: Path, rel: str) -> Path | None:
    if not isinstance(rel, str) or not rel.strip():
        return None
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def validate_brain_data(
    manifest: dict,
    router: dict,
    plugins: dict,
    *,
    root: Path = REPO_ROOT,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(manifest, dict):
        return ['manifest must be a mapping'], warnings
    if manifest.get('checkpoint_id') != 'GITHUB_BRAIN_V2':
        errors.append("manifest.checkpoint_id must be 'GITHUB_BRAIN_V2'")
    if manifest.get('version') != '2.0.0':
        errors.append("manifest.version must be '2.0.0'")
    aliases = manifest.get('activation_aliases', [])
    if not isinstance(aliases, list) or 'GITHUB_BRAIN_V1' not in aliases:
        errors.append('manifest.activation_aliases must keep GITHUB_BRAIN_V1 compatibility')

    expected_paths = {
        'checkpoint_path': 'AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md',
        'router_path': 'AI_SKILL_LIBRARY/router.yaml',
        'plugins_path': 'AI_SKILL_LIBRARY/plugins.yaml',
        'registry_path': 'AI_SKILL_LIBRARY/sources.yaml',
        'validator_path': 'AI_SKILL_LIBRARY/validate_brain.py',
    }
    for key, expected in expected_paths.items():
        if manifest.get(key) != expected:
            errors.append(f'manifest.{key} must be {expected!r}')
        path = _inside_root(root, expected)
        if path is None or not path.is_file():
            errors.append(f'manifest target missing: {expected}')

    if not isinstance(router, dict) or router.get('version') != 2:
        errors.append('router.version must be 2')
        return errors, warnings
    defaults = router.get('defaults')
    if not isinstance(defaults, dict):
        errors.append('router.defaults must be a mapping')
        defaults = {}
    max_domain = defaults.get('max_domain_skills')
    if not isinstance(max_domain, int) or max_domain < 1:
        errors.append('router.defaults.max_domain_skills must be a positive integer')
        max_domain = 3
    if defaults.get('preload_all_skills') is not False:
        errors.append('router.defaults.preload_all_skills must be false')
    if defaults.get('preload_trading_state') is not False:
        errors.append('router.defaults.preload_trading_state must be false')

    plugin_entries = plugins.get('plugins', []) if isinstance(plugins, dict) else []
    plugin_caps: set[str] = set()
    for idx, plugin in enumerate(plugin_entries, start=1):
        if not isinstance(plugin, dict):
            errors.append(f'plugin[{idx}] must be a mapping')
            continue
        cap = plugin.get('capability')
        if not isinstance(cap, str) or not cap:
            errors.append(f'plugin[{idx}] capability must be non-empty')
        elif cap in plugin_caps:
            errors.append(f'plugin[{idx}] duplicate capability {cap!r}')
        else:
            plugin_caps.add(cap)

    skills = router.get('skills', [])
    if not isinstance(skills, list) or not skills:
        errors.append('router.skills must be a non-empty list')
        skills = []
    ids: set[str] = set()
    skill_rows: dict[str, dict] = {}
    for idx, skill in enumerate(skills, start=1):
        if not isinstance(skill, dict):
            errors.append(f'skill[{idx}] must be a mapping')
            continue
        sid = skill.get('id')
        if not isinstance(sid, str) or not sid:
            errors.append(f'skill[{idx}] id must be non-empty')
            continue
        if sid in ids:
            errors.append(f'skill[{idx}] duplicate skill id {sid!r}')
        ids.add(sid)
        skill_rows[sid] = skill
        path = _inside_root(root, skill.get('path'))
        if path is None or not path.is_file():
            errors.append(f'skill[{sid}] path missing or outside repo: {skill.get("path")!r}')
        priority = skill.get('priority')
        if not isinstance(priority, int):
            errors.append(f'skill[{sid}] priority must be an integer')
        for cap in skill.get('plugin_ids', []):
            if cap not in plugin_caps:
                errors.append(f'skill[{sid}] unknown plugin capability {cap!r}')

    for sid, skill in skill_rows.items():
        for field in ('requires', 'conflicts_with'):
            refs = skill.get(field, [])
            if not isinstance(refs, list):
                errors.append(f'skill[{sid}] {field} must be a list')
                continue
            for ref in refs:
                if ref not in ids:
                    errors.append(f'skill[{sid}] {field} references unknown skill {ref!r}')
                if ref == sid:
                    errors.append(f'skill[{sid}] cannot {field} itself')

    routes = router.get('routes', [])
    route_ids: set[str] = set()
    for idx, route in enumerate(routes, start=1):
        if not isinstance(route, dict):
            errors.append(f'route[{idx}] must be a mapping')
            continue
        rid = route.get('id')
        if not isinstance(rid, str) or not rid:
            errors.append(f'route[{idx}] id must be non-empty')
            continue
        if rid in route_ids:
            errors.append(f'route[{idx}] duplicate route id {rid!r}')
        route_ids.add(rid)
        selected = [route.get('primary')] + list(route.get('supporting', []))
        for sid in selected:
            if sid not in ids:
                errors.append(f'route[{rid}] references unknown skill {sid!r}')
        domain_selected = [sid for sid in selected if sid not in {'critical_thinking', 'verification'}]
        if len(domain_selected) > max_domain:
            errors.append(
                f'route[{rid}] selects {len(domain_selected)} domain skills; max is {max_domain}'
            )
        selected_set = set(selected)
        for sid in selected_set & ids:
            conflicts = set(skill_rows[sid].get('conflicts_with', []))
            collision = conflicts & selected_set
            if collision:
                errors.append(f'route[{rid}] contains conflicting skills {sid!r} and {sorted(collision)!r}')

    authorities = router.get('authorities', [])
    if not isinstance(authorities, list) or not authorities:
        errors.append('router.authorities must be a non-empty list')
        authorities = []
    by_scope: dict[str, list[dict]] = {}
    for idx, authority in enumerate(authorities, start=1):
        if not isinstance(authority, dict):
            errors.append(f'authority[{idx}] must be a mapping')
            continue
        scope = authority.get('scope')
        if not isinstance(scope, str) or not scope:
            errors.append(f'authority[{idx}] scope must be non-empty')
            continue
        by_scope.setdefault(scope, []).append(authority)
        path = _inside_root(root, authority.get('path'))
        if path is None or not path.is_file():
            errors.append(f'authority[{scope}] path missing or outside repo: {authority.get("path")!r}')
        follows = authority.get('follows')
        if follows:
            follow_path = _inside_root(root, follows)
            if follow_path is None or not follow_path.is_file():
                errors.append(f'authority[{scope}] follows missing or outside repo: {follows!r}')

    for scope, entries in by_scope.items():
        current = [e for e in entries if e.get('status') == 'CURRENT_AUTHORITY']
        if len(current) > 1:
            errors.append(f'multiple current authorities for scope {scope!r}')
        elif len(current) == 0:
            errors.append(f'no current authority for scope {scope!r}')

    return errors, warnings


def _load() -> tuple[dict, dict, dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    router = yaml.safe_load(ROUTER_PATH.read_text(encoding='utf-8'))
    plugins = yaml.safe_load(PLUGINS_PATH.read_text(encoding='utf-8'))
    return manifest, router, plugins


def main() -> int:
    try:
        manifest, router, plugins = _load()
    except (FileNotFoundError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f'[ERROR] unable to load V2 brain files: {exc}', file=sys.stderr)
        return 2
    errors, warnings = validate_brain_data(manifest, router, plugins)
    for warning in warnings:
        print(f'[WARN ] {warning}')
    for error in errors:
        print(f'[ERROR] {error}', file=sys.stderr)
    print(f'Brain validation summary: {len(errors)} error(s), {len(warnings)} warning(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
