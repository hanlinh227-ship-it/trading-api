#!/usr/bin/env python3
"""Validate a compiled Skill-Mandatory Fast Gateway snapshot."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SENSITIVE_KEY_RE = re.compile(r"secret|token|password|private_key|api_key|credential", re.I)


def _walk_sensitive(value: Any, path: str = "snapshot") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                errors.append(f"sensitive-shaped key forbidden at {path}.{key}")
            errors.extend(_walk_sensitive(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_walk_sensitive(item, f"{path}[{index}]"))
    return errors


def validate_snapshot(snapshot: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors = [f"schema: {issue.message}" for issue in Draft202012Validator(schema).iter_errors(snapshot)]
    skills = snapshot.get("skills", {}) if isinstance(snapshot, dict) else {}
    capsules = snapshot.get("capsules", {}) if isinstance(snapshot, dict) else {}
    aliases = snapshot.get("aliases", {}) if isinstance(snapshot, dict) else {}
    fallback = snapshot.get("fallback_primary_skill") if isinstance(snapshot, dict) else None
    if fallback not in skills:
        errors.append("fallback primary skill missing from skills")
    if fallback not in capsules:
        errors.append("fallback primary skill missing from capsules")
    for skill_id in skills:
        if skill_id not in capsules:
            errors.append(f"skill missing capsule: {skill_id}")
    for skill_id, capsule in capsules.items():
        if skill_id not in skills:
            errors.append(f"orphan capsule: {skill_id}")
            continue
        if not isinstance(capsule, dict) or capsule.get("skill_id") != skill_id:
            errors.append(f"capsule identity mismatch: {skill_id}")
    for skill_id in aliases:
        if skill_id not in skills:
            errors.append(f"alias references unknown skill: {skill_id}")
    fast = snapshot.get("profiles", {}).get("FAST", {}) if isinstance(snapshot, dict) else {}
    if fast.get("max_supporting_skills") != 0:
        errors.append("FAST must allow zero supporting skills")
    if fast.get("tool_candidates") != 0:
        errors.append("FAST must preload zero tool candidates")
    if fast.get("durable_memory_items") != 0:
        errors.append("FAST must preload zero durable memory items")
    policy = snapshot.get("routing_policy", {}) if isinstance(snapshot, dict) else {}
    if policy.get("no_network_fast_selection") is not True:
        errors.append("FAST no-network selection invariant missing")
    errors.extend(_walk_sensitive(snapshot))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot")
    parser.add_argument("--schema", default="AI_SKILL_LIBRARY/v4/schemas/skill_gateway_snapshot.schema.json")
    args = parser.parse_args()
    snapshot_path = Path(args.snapshot)
    schema_path = Path(args.schema)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_snapshot(snapshot, schema)
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"Skill gateway snapshot validation summary: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
