from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
_PRIVILEGED_TERMS = (
    "enable shell",
    "run bash",
    "disable security",
    "ignore brain policy",
    "bypass permission",
    "widen permission",
)
_CREDENTIAL_PATTERNS = (
    re.compile(r"authorization\s*:\s*bearer\s+\S+", re.I),
    re.compile(r"\bapi[_ -]?key\b\s*[:=]\s*\S+", re.I),
    re.compile(r"\bprivate[_ -]?key\b\s*[:=]\s*\S+", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _walk(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, key, item
            yield from _walk(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{prefix}[{index}]")


def validate_untrusted_text(text: str) -> list[str]:
    lowered = str(text or "").lower()
    if any(term in lowered for term in _PRIVILEGED_TERMS):
        return ["untrusted_instruction: external content attempts to alter Brain policy or privileged execution"]
    return []


def validate_worker_output(output: Any) -> list[str]:
    try:
        serialized = json.dumps(output, ensure_ascii=False, sort_keys=True)
    except TypeError:
        serialized = str(output)
    errors: list[str] = []
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(serialized):
            errors.append("credential_material: worker output contains credential-like material")
            break
    return errors


def _external_scopes(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, dict):
        return {str(key) for key, action in value.items() if str(action).lower() in {"allow", "ask", "true", "1"}}
    return set()


def validate_candidate(candidate: dict, *, baseline_permissions: dict | None = None) -> list[str]:
    errors: list[str] = []
    baseline_permissions = baseline_permissions or {}
    for path, key, value in _walk(candidate):
        key_text = str(key).lower()
        if key_text in {"financial_execution", "live_financial_execution"} and value is True:
            errors.append(f"financial_execution: forbidden candidate capability at {path}")
        if key_text in {"permission_widening", "expand_permissions", "permission_expansion"} and value is True:
            errors.append(f"permission_widening: candidate attempts permission expansion at {path}")
        if key_text == "external_directory":
            requested = _external_scopes(value)
            baseline = _external_scopes(baseline_permissions.get("external_directory"))
            extra = sorted(requested - baseline)
            if extra:
                errors.append(f"external_directory: candidate expands filesystem scope: {extra}")
    errors.extend(validate_worker_output(candidate))
    return sorted(set(errors))


def validate_idle_job(job: dict) -> list[str]:
    errors: list[str] = []
    kind = str(job.get("kind", "")).lower()
    if kind in {"permission_change", "credential_mutation", "live_financial_execution", "destructive_production"}:
        errors.append(f"permission_or_high_risk_job: idle learning cannot execute {kind}")
    for path, key, value in _walk(job):
        if str(key).lower() in {"permission_widening", "expand_permissions", "permission_expansion"} and value is True:
            errors.append(f"permission_widening: idle learning cannot widen permissions at {path}")
    return sorted(set(errors))


def validate_legion(root: Path) -> list[str]:
    root = Path(root).resolve()
    errors: list[str] = []
    learning_policy = _load_yaml(root / "AI_SKILL_LIBRARY/v4/learning/policy.yaml")
    sources = _load_yaml(root / "AI_SKILL_LIBRARY/v4/learning/sources.yaml")
    legion_policy = _load_yaml(root / "AI_SKILL_LIBRARY/v4/legion/policy.yaml")

    if learning_policy.get("fixed_layer_priority") != "forbidden":
        errors.append("fixed_layer_priority: learning layers must remain peers")
    if learning_policy.get("majority_vote_for_truth") != "forbidden":
        errors.append("majority_vote: truth may not be determined by voting")
    if learning_policy.get("permission_expansion_by_learning") != "forbidden":
        errors.append("permission_widening: learning must not expand its own permissions")
    if learning_policy.get("risk_taxonomy_is_separate") is not True:
        errors.append("risk_taxonomy: learning layers must remain separate from risk classes")

    expected_layers = {"experience", "curated", "exploration"}
    layers = sources.get("layers") if isinstance(sources.get("layers"), dict) else {}
    if set(layers) != expected_layers:
        errors.append("learning_layers: expected exactly experience, curated, exploration")
    for layer_name, layer in layers.items():
        if not isinstance(layer, dict):
            errors.append(f"learning_layer: {layer_name} must be an object")
            continue
        if layer.get("epistemic_priority", layer.get("epistemic_status")) != "peer":
            errors.append(f"learning_layer: {layer_name} must have peer epistemic status")
        for forbidden_key in ("weight", "fixed_weight", "priority", "fixed_priority"):
            if forbidden_key in layer:
                errors.append(f"weight: fixed layer weighting is forbidden ({layer_name}.{forbidden_key})")

    if legion_policy.get("single_commander") is not True or legion_policy.get("commander") != "GITHUB_BRAIN_V4":
        errors.append("authority: GITHUB_BRAIN_V4 must remain the single commander")
    if legion_policy.get("routing_authority") is not False or legion_policy.get("reasoning_authority") is not False:
        errors.append("authority: Legion must not gain routing or reasoning authority")
    if legion_policy.get("live_financial_execution") is not False:
        errors.append("financial_execution: Legion default must remain research-only")
    if legion_policy.get("permission_widening") != "forbidden":
        errors.append("permission_widening: Legion policy must forbid permission widening")

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    errors = validate_legion(Path(args.root))
    for item in errors:
        print(f"[ERROR] {item}")
    print(f"LEGION_VALIDATE={'PASS' if not errors else 'FAIL'} failures={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
