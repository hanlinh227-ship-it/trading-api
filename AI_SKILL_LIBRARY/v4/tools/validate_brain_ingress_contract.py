"""Validate the authority-free ChatGPT→Brain ingress/response contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


def validate_contract(contract_path: Path, schema_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        contract = yaml.safe_load(Path(contract_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"cannot load ChatGPT Brain contract: {exc}"]

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"invalid ChatGPT Brain schema: {exc}"]

    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"schema {location}: {error.message}")

    if not isinstance(contract, dict):
        return errors or ["contract root must be an object"]

    authority = contract.get("authority") if isinstance(contract.get("authority"), dict) else {}
    if authority and any(value is not False for value in authority.values()):
        errors.append("ChatGPT ingress contract must have zero authority")

    ingress = contract.get("ingress") if isinstance(contract.get("ingress"), dict) else {}
    if ingress.get("mandatory_next_hop") != "task_router":
        errors.append("ingress must route to task_router first")
    if ingress.get("may_choose_model") is not False:
        errors.append("ingress may not choose a model directly")
    if ingress.get("may_bypass_task_router") is not False:
        errors.append("ingress may not bypass task_router")
    if ingress.get("may_widen_permissions") is not False:
        errors.append("ingress may not widen permissions")

    response = contract.get("response") if isinstance(contract.get("response"), dict) else {}
    if response.get("hidden_reasoning_allowed") is not False:
        errors.append("response contract must not expose hidden reasoning")

    privacy = contract.get("privacy") if isinstance(contract.get("privacy"), dict) else {}
    secret = privacy.get("SECRET") if isinstance(privacy.get("SECRET"), dict) else {}
    confidential = privacy.get("CONFIDENTIAL") if isinstance(privacy.get("CONFIDENTIAL"), dict) else {}
    if secret.get("default_route") != "local_only":
        errors.append("SECRET must default to local_only")
    if confidential.get("default_route") != "local_preferred":
        errors.append("CONFIDENTIAL must default to local_preferred")
    if confidential.get("external_requires_verified_policy") is not True:
        errors.append("CONFIDENTIAL external routing requires verified policy")
    if privacy.get("free_external_sensitive_default") is not False:
        errors.append("sensitive content must not default to free external providers")

    return errors


def validate_brain_ingress_contract(root: Path) -> list[str]:
    root = Path(root).resolve()
    contract_path = root / "AI_SKILL_LIBRARY/v4/control_plane/chatgpt_brain_contract.yaml"
    schema_path = root / "AI_SKILL_LIBRARY/v4/schemas/chatgpt_brain_contract.schema.json"
    errors: list[str] = []
    if not contract_path.is_file():
        errors.append(f"missing ChatGPT Brain contract: {contract_path.relative_to(root)}")
    if not schema_path.is_file():
        errors.append(f"missing ChatGPT Brain schema: {schema_path.relative_to(root)}")
    if errors:
        return errors
    return validate_contract(contract_path, schema_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ChatGPT→Brain ingress contract")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    errors = validate_brain_ingress_contract(Path(args.root))
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"CHATGPT_BRAIN_INGRESS_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
