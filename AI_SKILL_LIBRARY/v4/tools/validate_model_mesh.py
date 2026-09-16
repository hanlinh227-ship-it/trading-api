from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import re
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
    "private_key", "wallet_seed", "credential", "authorization", "secret_value",
}
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
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


def _credential_like_values(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            found.extend(_credential_like_values(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_credential_like_values(nested, f"{path}[{index}]"))
    elif isinstance(value, str):
        if re.search(r"(?:sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9_-]{8,}|Bearer\s+\S+)", value):
            found.append(path)
    return found


def validate_model_mesh(root: Path) -> list[str]:
    root = Path(root).resolve()
    errors: list[str] = []
    mesh_root = root / "AI_SKILL_LIBRARY/v4/model_mesh"
    required_yaml = {
        "policy": mesh_root / "policy.yaml",
        "providers": mesh_root / "providers.yaml",
        "discovery": mesh_root / "discovery.yaml",
        "capabilities": mesh_root / "domain_capabilities.yaml",
        "upstreams": mesh_root / "upstreams.yaml",
    }
    required_json = {
        "active": mesh_root / "active.json",
        "runtime_bindings": mesh_root / "runtime_bindings.json",
        "free_only_policy": mesh_root / "free_only_policy.json",
    }
    documents: dict[str, dict] = {}
    for name, path in required_yaml.items():
        if not path.is_file():
            errors.append(f"missing model mesh contract: {path.relative_to(root)}")
            continue
        try:
            documents[name] = _yaml(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))
    for name, path in required_json.items():
        if not path.is_file():
            errors.append(f"missing model mesh contract: {path.relative_to(root)}")
            continue
        try:
            documents[name] = _json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

    policy = documents.get("policy", {})
    if policy:
        if policy.get("mode") != "FREE_ONLY": errors.append("model mesh policy mode must be FREE_ONLY")
        if policy.get("routing_authority") is not False or policy.get("reasoning_authority") is not False: errors.append("model mesh policy must have zero routing/reasoning authority")
        if policy.get("stable_request_dependency") is not False: errors.append("Stable requests must not depend on model mesh discovery")
        if policy.get("max_parallel") != {"FAST": 0, "STANDARD": 2, "DEEP": 4}: errors.append("model mesh parallel limits must remain FAST=0 STANDARD=2 DEEP=4")
        if policy.get("provider_voting") != "forbidden": errors.append("provider voting must remain forbidden")
        if policy.get("quota", {}).get("circumvention_forbidden") is not True: errors.append("quota circumvention must remain forbidden")
        if policy.get("paid_fallback") != "disabled" or policy.get("auto_purchase") is not False: errors.append("FREE_ONLY policy must forbid paid fallback and auto purchase")

    capabilities = documents.get("capabilities", {})
    if capabilities:
        if set(capabilities.get("dimensions", [])) != EXPECTED_DIMENSIONS: errors.append("model mesh capability dimensions do not match canonical set")
        if set(capabilities.get("domains", {})) != EXPECTED_DOMAINS: errors.append("model mesh domain capability map does not cover canonical domains exactly")
        if capabilities.get("domains", {}).get("trading", {}).get("research_only") is not True: errors.append("trading model mesh capability must remain research_only")

    discovery = documents.get("discovery", {})
    if discovery:
        if discovery.get("plane") != "evergreen_only": errors.append("model mesh discovery must remain Evergreen-only")
        if discovery.get("stable_request_dependency") is not False: errors.append("model mesh discovery cannot be a Stable request dependency")
        output = discovery.get("output", {})
        if output.get("state") != "quarantine" or output.get("routing_authority") is not False or output.get("stable_mutation") is not False: errors.append("model mesh discovery output must remain quarantine-only with zero authority")
        rules = discovery.get("policy", {})
        for key in ("catalog_presence_is_not_free_entitlement", "zero_price_metadata_is_not_account_entitlement", "free_label_is_not_account_entitlement"):
            if rules.get(key) is not True: errors.append(f"model mesh discovery must preserve {key}")

    providers = documents.get("providers", {})
    provider_ids = set(providers.get("providers", {})) if providers else set()
    if providers:
        if providers.get("policy", {}).get("evidence_is_not_entitlement") is not True: errors.append("provider docs/catalogs must remain evidence, not entitlement")
        if providers.get("policy", {}).get("unknown_free_status") != "exclude": errors.append("unknown provider free status must be excluded")
        if len(provider_ids) < 8: errors.append("provider evidence registry is unexpectedly incomplete")

    active = documents.get("active", {})
    free_only_policy = documents.get("free_only_policy", {})
    eligible_statuses = set(free_only_policy.get("eligible_statuses", []))
    if free_only_policy:
        if free_only_policy.get("schema_version") != 2 or free_only_policy.get("mode") != "FREE_ONLY": errors.append("canonical FREE_ONLY policy metadata invalid")
        # FREE_ONLY admits every class that is provably zero-cost at execution
        # time, and no class that can become billable without a hard stop.
        if eligible_statuses != {"recurring", "account_specific", "temporary_zero_price", "free_quota_hard_stop"}:
            errors.append("canonical FREE_ONLY statuses must be the four zero-cost classes")
        billable = eligible_statuses & {"paid", "trial_credit", "limited_time", "expired", "unknown"}
        if billable: errors.append(f"canonical FREE_ONLY policy admits billable statuses: {sorted(billable)}")
        requirements = free_only_policy.get("requirements", {})
        for flag in ("auto_purchase_forbidden", "paid_fallback_forbidden", "hard_stop_required_for_finite_free_quota", "price_revalidation_required_for_temporary_zero_price"):
            if requirements.get(flag) is not True: errors.append(f"canonical FREE_ONLY policy must set {flag}")
        failure_policy = free_only_policy.get("failure_policy", {})
        for code, action in (("402", "quarantine_model_and_failover"), ("404", "discover_probe_replacement"), ("410", "discover_probe_replacement"), ("429", "cooldown_and_failover")):
            if failure_policy.get(code) != action: errors.append(f"canonical FREE_ONLY failure policy for {code} must be {action}")
        if free_only_policy.get("model_level_eligibility", {}).get("provider_blacklist_on_single_model_failure") is not False:
            errors.append("a single model failure must never blacklist a whole provider")
        if free_only_policy.get("free_verified_at_required") is not True: errors.append("canonical FREE_ONLY policy must require verification evidence")
    if active:
        if active.get("version") != 1 or active.get("mode") != "FREE_ONLY": errors.append("active model registry must be version 1 FREE_ONLY")
        if active.get("routing_authority") is not False or active.get("reasoning_authority") is not False: errors.append("active model registry must have zero authority")
        rows = active.get("models")
        if not isinstance(rows, list) or not rows: errors.append("active model registry must contain at least one model")
        else:
            for row in rows:
                if not isinstance(row, dict): errors.append("invalid active model row"); continue
                pid = row.get("provider_id")
                if pid not in provider_ids: errors.append(f"active model provider is not registered: {pid}")
                if row.get("provider_class") == "Q": errors.append(f"quarantine provider cannot be active: {pid}")
                if row.get("free_status") not in eligible_statuses and row.get("registry_state") != "NOT_ELIGIBLE": errors.append(f"ineligible model must be explicitly demoted: {pid}:{row.get('model_id')}")
                demoted = row.get("registry_state") == "NOT_ELIGIBLE"
                if not demoted and row.get("free_status") in eligible_statuses and (not row.get("free_verified_at") or not row.get("source_evidence")): errors.append(f"eligible model lacks entitlement evidence: {pid}:{row.get('model_id')}")
                if not demoted and row.get("free_status") in eligible_statuses:
                    zero_cost = row.get("zero_cost")
                    if not isinstance(zero_cost, dict):
                        errors.append(f"eligible model lacks zero-cost evidence: {pid}:{row.get('model_id')}")
                    else:
                        for field in ("input_price_per_million", "output_price_per_million"):
                            price = zero_cost.get(field)
                            if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0:
                                errors.append(f"eligible model is not zero-price: {pid}:{row.get('model_id')}")
                        finite = row.get("free_status") == "free_quota_hard_stop" or zero_cost.get("quota_model") == "finite"
                        if finite and zero_cost.get("hard_stop_verified") is not True:
                            errors.append(f"finite free quota without a verified hard stop: {pid}:{row.get('model_id')}")
                        if row.get("free_status") == "temporary_zero_price" and not zero_cost.get("price_verified_at"):
                            errors.append(f"temporary zero price without price evidence: {pid}:{row.get('model_id')}")
                        expires = str(zero_cost.get("free_quota_expires_at") or "").strip()
                        if expires:
                            try:
                                expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                            except ValueError:
                                errors.append(f"free quota expiry is not ISO-8601: {pid}:{row.get('model_id')}")
                            else:
                                if expiry.tzinfo is None:
                                    expiry = expiry.replace(tzinfo=timezone.utc)
                                if expiry <= datetime.now(timezone.utc):
                                    errors.append(f"free quota already expired: {pid}:{row.get('model_id')} expired_at={expires}")

    bindings_doc = documents.get("runtime_bindings", {})
    if bindings_doc:
        if bindings_doc.get("version") != 1 or bindings_doc.get("mode") != "FREE_ONLY": errors.append("runtime bindings must be version 1 FREE_ONLY")
        bindings = bindings_doc.get("bindings")
        if not isinstance(bindings, dict) or not bindings: errors.append("runtime bindings must be non-empty")
        else:
            for pid, row in bindings.items():
                if pid not in provider_ids: errors.append(f"runtime binding provider is not registered: {pid}")
                if not isinstance(row, dict): errors.append(f"invalid runtime binding: {pid}"); continue
                if row.get("enabled") is not True: continue
                if not str(row.get("endpoint_url") or "").startswith("https://"): errors.append(f"runtime binding endpoint must be https: {pid}")
                if row.get("endpoint_family") not in {"openai_compatible", "gemini", "cloudflare_ai"}: errors.append(f"unsupported runtime endpoint family: {pid}")
                secret_name = str(row.get("secret_name") or "")
                if not ENV_NAME_RE.fullmatch(secret_name): errors.append(f"invalid runtime secret env name: {pid}")
                account_env = row.get("account_id_env")
                if account_env is not None and not ENV_NAME_RE.fullmatch(str(account_env)): errors.append(f"invalid runtime account env name: {pid}")

    upstreams = documents.get("upstreams", {})
    if upstreams:
        sources = upstreams.get("sources", [])
        if not isinstance(sources, list) or not sources: errors.append("model mesh upstream references are missing")
        else:
            for row in sources:
                if not isinstance(row, dict): errors.append("invalid upstream reference row"); continue
                if row.get("routing_authority") is not False or row.get("reasoning_authority") is not False: errors.append(f"upstream {row.get('id')} gained authority")
                if row.get("mandatory_runtime_dependency") is not False or row.get("code_reuse") is not False: errors.append(f"upstream {row.get('id')} became a mandatory/code-reuse dependency")
                if not row.get("license"): errors.append(f"upstream {row.get('id')} missing license")

    for name, document in documents.items():
        paths = _credential_paths(document)
        if paths: errors.append(f"{name} contains forbidden credential fields: {', '.join(paths[:8])}")
        value_paths = _credential_like_values(document)
        if value_paths: errors.append(f"{name} contains credential-like values: {', '.join(value_paths[:8])}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Adaptive Free Model Mesh stable contracts")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    errors = validate_model_mesh(Path(args.root))
    for item in errors: print(f"[ERROR] {item}")
    print(f"MODEL_MESH_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
