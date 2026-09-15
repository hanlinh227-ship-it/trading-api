from __future__ import annotations

import argparse
from pathlib import Path

import yaml


EXPECTED_DOMAINS = {
    "core", "engineering", "trading", "game", "design_2d", "design_3d",
    "adobe", "prompt_media", "writing", "academic", "data_docs", "business",
}
EXPECTED_DIMENSIONS = {
    "text_reasoning", "coding", "math_quant", "long_context", "multilingual",
    "vision", "structured_output", "tool_calling", "planning", "creative_writing",
    "prompt_media", "research_synthesis", "data_analysis", "low_latency",
}
FORBIDDEN_CREDENTIAL_KEYS = {
    "api_key", "apikey", "access_token", "auth_token", "bearer_token", "password",
    "private_key", "wallet_seed", "credential", "authorization",
}


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _credential_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).strip().lower()
            child = f"{path}.{key}"
            if key_text in FORBIDDEN_CREDENTIAL_KEYS:
                found.append(child)
            found.extend(_credential_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_credential_paths(nested, f"{path}[{index}]"))
    return found


def validate_model_mesh(root: Path) -> list[str]:
    root = Path(root).resolve()
    errors: list[str] = []
    mesh_root = root / "AI_SKILL_LIBRARY/v4/model_mesh"
    required = {
        "policy": mesh_root / "policy.yaml",
        "providers": mesh_root / "providers.yaml",
        "discovery": mesh_root / "discovery.yaml",
        "capabilities": mesh_root / "domain_capabilities.yaml",
        "upstreams": mesh_root / "upstreams.yaml",
    }
    documents: dict[str, dict] = {}
    for name, path in required.items():
        if not path.is_file():
            errors.append(f"missing model mesh contract: {path.relative_to(root)}")
            continue
        try:
            documents[name] = _yaml(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))

    policy = documents.get("policy", {})
    if policy:
        if policy.get("mode") != "FREE_ONLY":
            errors.append("model mesh policy mode must be FREE_ONLY")
        if policy.get("routing_authority") is not False or policy.get("reasoning_authority") is not False:
            errors.append("model mesh policy must have zero routing/reasoning authority")
        if policy.get("stable_request_dependency") is not False:
            errors.append("Stable requests must not depend on model mesh discovery")
        if policy.get("max_parallel") != {"FAST": 0, "STANDARD": 2, "DEEP": 4}:
            errors.append("model mesh parallel limits must remain FAST=0 STANDARD=2 DEEP=4")
        if policy.get("provider_voting") != "forbidden":
            errors.append("provider voting must remain forbidden")
        if policy.get("quota", {}).get("circumvention_forbidden") is not True:
            errors.append("quota circumvention must remain forbidden")
        if policy.get("paid_fallback") != "disabled" or policy.get("auto_purchase") is not False:
            errors.append("FREE_ONLY policy must forbid paid fallback and auto purchase")

    capabilities = documents.get("capabilities", {})
    if capabilities:
        if set(capabilities.get("dimensions", [])) != EXPECTED_DIMENSIONS:
            errors.append("model mesh capability dimensions do not match canonical set")
        if set(capabilities.get("domains", {})) != EXPECTED_DOMAINS:
            errors.append("model mesh domain capability map does not cover canonical domains exactly")
        if capabilities.get("domains", {}).get("trading", {}).get("research_only") is not True:
            errors.append("trading model mesh capability must remain research_only")

    discovery = documents.get("discovery", {})
    if discovery:
        if discovery.get("plane") != "evergreen_only":
            errors.append("model mesh discovery must remain Evergreen-only")
        if discovery.get("stable_request_dependency") is not False:
            errors.append("model mesh discovery cannot be a Stable request dependency")
        output = discovery.get("output", {})
        if output.get("state") != "quarantine" or output.get("routing_authority") is not False or output.get("stable_mutation") is not False:
            errors.append("model mesh discovery output must remain quarantine-only with zero authority")
        rules = discovery.get("policy", {})
        for key in ("catalog_presence_is_not_free_entitlement", "zero_price_metadata_is_not_account_entitlement", "free_label_is_not_account_entitlement"):
            if rules.get(key) is not True:
                errors.append(f"model mesh discovery must preserve {key}")

    providers = documents.get("providers", {})
    if providers:
        if providers.get("policy", {}).get("evidence_is_not_entitlement") is not True:
            errors.append("provider docs/catalogs must remain evidence, not entitlement")
        if providers.get("policy", {}).get("unknown_free_status") != "exclude":
            errors.append("unknown provider free status must be excluded")
        if len(providers.get("providers", {})) < 8:
            errors.append("provider evidence registry is unexpectedly incomplete")

    upstreams = documents.get("upstreams", {})
    if upstreams:
        sources = upstreams.get("sources", [])
        if not isinstance(sources, list) or not sources:
            errors.append("model mesh upstream references are missing")
        else:
            for row in sources:
                if not isinstance(row, dict):
                    errors.append("invalid upstream reference row")
                    continue
                if row.get("routing_authority") is not False or row.get("reasoning_authority") is not False:
                    errors.append(f"upstream {row.get('id')} gained authority")
                if row.get("mandatory_runtime_dependency") is not False or row.get("code_reuse") is not False:
                    errors.append(f"upstream {row.get('id')} became a mandatory/code-reuse dependency")
                if not row.get("license"):
                    errors.append(f"upstream {row.get('id')} missing license")

    for name, document in documents.items():
        paths = _credential_paths(document)
        if paths:
            errors.append(f"{name} contains forbidden credential fields: {', '.join(paths[:8])}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Adaptive Free Model Mesh stable contracts")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    errors = validate_model_mesh(Path(args.root))
    for item in errors:
        print(f"[ERROR] {item}")
    print(f"MODEL_MESH_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
