#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools.validate_skill_gateway_snapshot import validate_snapshot  # noqa: E402


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping: {path}")
    return data


def validate_skill_gateway(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        router = _yaml(root / "AI_SKILL_LIBRARY/v4/stable/router.yaml")
        runtime = _yaml(root / "AI_SKILL_LIBRARY/v4/stable/runtime.yaml")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"unable to load Skill Gateway policy: {exc}"]

    policy = router.get("policy", {})
    if policy.get("route_every_request") is not True:
        errors.append("every request must be routed")
    if policy.get("primary_skill_required") is not True:
        errors.append("primary_skill_required must be true")
    if policy.get("fallback_primary_skill") != "core_reasoning":
        errors.append("fallback_primary_skill must be core_reasoning")
    if policy.get("skill_execution_capsule_required") is not True:
        errors.append("skill_execution_capsule_required must be true")

    profiles = runtime.get("profiles", {})
    for name in ("FAST", "STANDARD", "DEEP"):
        row = profiles.get(name, {})
        if row.get("primary_skill_count") != 1:
            errors.append(f"{name} must require exactly one primary skill")
        if row.get("skill_capsule_required") is not True:
            errors.append(f"{name} must require an execution capsule")
    if profiles.get("FAST", {}).get("max_supporting_skills") != 0:
        errors.append("FAST must use zero supporting skills")
    if profiles.get("FAST", {}).get("tool_candidates") != 0:
        errors.append("FAST must not preload tools")
    if profiles.get("FAST", {}).get("durable_memory_items") != 0:
        errors.append("FAST must not preload durable memory")

    if errors:
        return errors
    try:
        snapshot = compile_snapshot(root, "0" * 40, generated_at="1970-01-01T00:00:00Z")
    except Exception as exc:
        return [f"Skill Gateway snapshot compilation failed: {exc}"]
    errors.extend(validate_snapshot(snapshot, root))
    return errors


def main() -> int:
    errors = validate_skill_gateway()
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    print(f"Skill Gateway validation summary: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
