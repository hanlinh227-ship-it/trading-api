from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "AI_SKILL_LIBRARY/v4/schemas/skill_gateway_snapshot.schema.json"
SENSITIVE_KEY_RE = re.compile(r"(?:^|_)(?:secret|password|private_key|api_key|credential|token)(?:$|_)", re.I)


def _canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _scan_sensitive(value, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                errors.append(f"sensitive key forbidden at {path}.{key}")
            errors.extend(_scan_sensitive(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_scan_sensitive(child, f"{path}[{index}]") )
    return errors


def validate_snapshot(snapshot: dict, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    root = Path(root).resolve()
    try:
        schema = json.loads((root / "AI_SKILL_LIBRARY/v4/schemas/skill_gateway_snapshot.schema.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"snapshot schema load error: {exc}"]

    for issue in Draft202012Validator(schema).iter_errors(snapshot):
        errors.append(f"snapshot schema: {issue.message}")
    if not isinstance(snapshot, dict):
        return errors or ["snapshot must be an object"]

    skills = snapshot.get("skills", {}) if isinstance(snapshot.get("skills"), dict) else {}
    capsules = snapshot.get("capsules", {}) if isinstance(snapshot.get("capsules"), dict) else {}
    aliases = snapshot.get("routing_aliases", {}) if isinstance(snapshot.get("routing_aliases"), dict) else {}
    fallback = snapshot.get("fallback_primary_skill")

    if fallback != "core_reasoning":
        errors.append("fallback primary skill must be core_reasoning")
    if fallback not in skills:
        errors.append("fallback primary skill missing from skills")
    if fallback not in capsules:
        errors.append("fallback primary skill missing capsule")

    for sid in aliases:
        if sid not in skills:
            errors.append(f"unknown alias skill: {sid}")
    for sid in capsules:
        if sid not in skills:
            errors.append(f"capsule references unknown skill: {sid}")
    for sid, meta in skills.items():
        if sid == "task_router":
            continue
        if sid not in capsules:
            errors.append(f"skill missing execution capsule: {sid}")
        if isinstance(meta, dict) and meta.get("primary_selectable") is True:
            domain = meta.get("domain")
            domains = snapshot.get("domains", {})
            if not isinstance(domains, dict) or sid not in domains.get(domain, []):
                errors.append(f"primary skill/domain mismatch: {sid} -> {domain}")

    for sid, capsule in capsules.items():
        if not isinstance(capsule, dict):
            errors.append(f"invalid capsule mapping: {sid}")
            continue
        if capsule.get("skill_id") != sid:
            errors.append(f"capsule skill id mismatch: {sid}")
        expected = capsule.get("capsule_hash")
        bare = {key: value for key, value in capsule.items() if key != "capsule_hash"}
        actual = _canonical_hash(bare)
        if expected != actual:
            errors.append(f"capsule hash mismatch: {sid}")
        if not str(capsule.get("output_contract") or "").strip():
            errors.append(f"capsule output contract missing: {sid}")

    profiles = snapshot.get("profiles", {}) if isinstance(snapshot.get("profiles"), dict) else {}
    for name in ("FAST", "STANDARD", "DEEP"):
        row = profiles.get(name)
        if not isinstance(row, dict):
            errors.append(f"missing profile: {name}")
            continue
        if row.get("primary_skill_count") != 1:
            errors.append(f"profile {name} must require exactly one primary skill")
        if row.get("skill_capsule_required") is not True:
            errors.append(f"profile {name} must require a skill capsule")
    if isinstance(profiles.get("FAST"), dict) and profiles["FAST"].get("max_supporting_skills") != 0:
        errors.append("FAST supporting skill count must be zero")

    errors.extend(_scan_sensitive(snapshot))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    path = Path(args.snapshot)
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] unable to load snapshot: {exc}")
        return 2
    errors = validate_snapshot(snapshot, Path(args.root))
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"Skill gateway snapshot validation summary: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
