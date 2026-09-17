"""Validate authority-safe ChatGPT -> Brain ingress/response contracts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


FORBIDDEN_INGRESS_FIELDS = {"selected_model_ref", "model_id", "runtime_ref", "permission_override"}
EXPECTED_FLOW = [
    "ingress", "task_router", "project_domain_resolution", "memory", "skills",
    "model_mesh", "runtime_scheduler", "verifier", "synthesis", "response",
]


def validate_contracts(root: Path) -> list[str]:
    root = Path(root).resolve()
    contracts = root / "AI_SKILL_LIBRARY/v4/contracts"
    ingress_path = contracts / "chatgpt_brain_ingress.schema.json"
    response_path = contracts / "brain_response.schema.json"
    control_path = contracts / "chatgpt_brain_control_plane.yaml"
    errors: list[str] = []

    try:
        ingress = json.loads(ingress_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        control = yaml.safe_load(control_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"cannot load ChatGPT Brain contracts: {exc}"]

    for name, schema in (("ingress", ingress), ("response", response)):
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # pragma: no cover - jsonschema provides details
            errors.append(f"invalid {name} schema: {exc}")

    ingress_properties = set((ingress.get("properties") or {}).keys())
    leaked = sorted(FORBIDDEN_INGRESS_FIELDS & ingress_properties)
    if leaked:
        errors.append(f"ingress exposes forbidden control fields: {leaked}")
    if ingress.get("additionalProperties") is not False:
        errors.append("ingress must fail closed on undeclared fields")

    response_properties = set((response.get("properties") or {}).keys())
    if {"chain_of_thought", "hidden_reasoning"} & response_properties:
        errors.append("response contract must not expose hidden reasoning")
    if response.get("additionalProperties") is not False:
        errors.append("response must fail closed on undeclared fields")

    if not isinstance(control, dict):
        return errors + ["control-plane contract root must be a mapping"]
    if control.get("flow") != EXPECTED_FLOW:
        errors.append("control-plane flow must preserve task_router before model/runtime selection")
    invariants = control.get("invariants") if isinstance(control.get("invariants"), dict) else {}
    expected = {
        "task_router_mandatory": True,
        "ingress_may_choose_model": False,
        "ingress_may_bypass_router": False,
        "ingress_may_widen_permissions": False,
        "response_contains_hidden_reasoning": False,
        "registry_has_runtime_authority": False,
    }
    for key, value in expected.items():
        if invariants.get(key) is not value:
            errors.append(f"control-plane invariant {key} must be {value!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ChatGPT Brain control-plane contracts")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    errors = validate_contracts(Path(args.root))
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"CHATGPT_BRAIN_CONTRACTS_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
