"""Validate the authority-free Open Model Universe metadata registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
import yaml


RUNTIME_STATES = {"AVAILABLE", "DOWNLOADING", "CACHED", "WARM", "RUNNING", "SLEEPING", "DEGRADED", "EVICTED"}
FLOATING_REVISIONS = {"main", "master", "latest", "head", "trunk", "dev", "stable"}
FORBIDDEN_KEYS = {
    "api_key", "apikey", "access_token", "auth_token", "bearer_token", "password",
    "private_key", "wallet_seed", "credential", "authorization", "secret", "secret_value",
    "enabled",
}
CREDENTIAL_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{16}|Bearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
SENSITIVE_QUERY_KEYS = {"access_token", "api_key", "apikey", "auth", "authorization", "password", "secret", "token"}
URL_FIELDS = ("official_upstream", "weights_source", "license_url")
E2E_REQUIRED_FIELDS = (
    "immutable_revision", "artifact_url", "artifact_hash", "artifact_size_bytes",
    "artifact_format", "zero_cost_eligible", "offline_ready", "lineage",
    "artifact_security", "runtime_projection",
)


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas/open_model_universe.schema.json"


def _forbidden_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if str(key).strip().lower() in FORBIDDEN_KEYS:
                found.append(child)
            found.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    elif isinstance(value, str) and CREDENTIAL_VALUE.search(value):
        found.append(path)
    return found


def _unsafe_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parsed = urlsplit(value)
    except ValueError:
        return True
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        return True
    return any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True))


def _validate_e2e_candidate(model: dict, index: int) -> list[str]:
    errors: list[str] = []
    if model.get("admission_status") != "E2E_CANDIDATE":
        return errors
    missing = [field for field in E2E_REQUIRED_FIELDS if model.get(field) is None]
    if missing:
        errors.append(f"E2E candidate missing admission evidence at models[{index}]: {missing}")
    revision = str(model.get("upstream_revision") or "").strip()
    immutable = str(model.get("immutable_revision") or "").strip()
    if not revision or revision.lower() in FLOATING_REVISIONS or immutable != revision:
        errors.append(f"E2E candidate revision is not immutably pinned at models[{index}]")
    if model.get("license_verified") is not True or model.get("self_hostable") is not True:
        errors.append(f"E2E candidate must have verified licence and self-host rights at models[{index}]")
    if model.get("local_runtime_possible") is not True or model.get("paid_token_required") is not False:
        errors.append(f"E2E candidate must prove local zero-paid-token runtime eligibility at models[{index}]")
    security = model.get("artifact_security") if isinstance(model.get("artifact_security"), dict) else {}
    for key in ("revision_pinned", "digest_verified", "safe_format", "license_verified", "provenance_verified"):
        if security.get(key) is not True:
            errors.append(f"E2E candidate artifact_security.{key} must be true at models[{index}]")
    if security.get("trust_remote_code_required") is not False or security.get("custom_code_required") is not False:
        errors.append(f"first E2E candidate must not require remote/custom code at models[{index}]")
    projection = model.get("runtime_projection") if isinstance(model.get("runtime_projection"), dict) else {}
    mirrors = {
        "model_id": model.get("model_id"),
        "revision": model.get("upstream_revision"),
        "artifact_hash": model.get("artifact_hash"),
        "artifact_size_bytes": model.get("artifact_size_bytes"),
        "quantization": model.get("quantization"),
        "runtime_support": model.get("runtime_support"),
    }
    for key, expected in mirrors.items():
        if projection.get(key) != expected:
            errors.append(f"runtime_projection.{key} must mirror registry evidence at models[{index}]")
    return errors


def validate_document(document: object, schema: dict | None = None) -> list[str]:
    errors: list[str] = []
    if schema is None:
        schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"invalid Open Model Universe schema: {exc}"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"schema {location}: {error.message}")
    if not isinstance(document, dict):
        return errors or ["registry root must be an object"]

    policy = document.get("policy") if isinstance(document.get("policy"), dict) else {}
    if policy.get("cost_policy") != "OPEN_MODEL_ZERO_TOKEN_FIRST":
        errors.append("cost policy must be OPEN_MODEL_ZERO_TOKEN_FIRST")
    if policy.get("paid_fallback") != "NO_PAID_FALLBACK":
        errors.append("paid fallback must remain NO_PAID_FALLBACK")
    if policy.get("registry_implies_activation") is not False or policy.get("auto_download") is not False:
        errors.append("registry metadata must never imply activation or automatic download")

    authority = document.get("authority") if isinstance(document.get("authority"), dict) else {}
    if authority and any(value is not False for value in authority.values()):
        errors.append("Open Model Universe must have zero authority")

    identities: set[tuple[str, ...]] = set()
    model_ids: set[str] = set()
    models = document.get("models") if isinstance(document.get("models"), list) else []
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            continue
        identity = tuple(str(model.get(field) or "") for field in ("family", "base_model", "variant", "quantization", "runtime_build"))
        if identity in identities:
            errors.append(f"duplicate model identity at models[{index}]: {identity}")
        identities.add(identity)
        model_id = str(model.get("model_id") or "")
        if model_id in model_ids:
            errors.append(f"duplicate model_id at models[{index}]: {model_id}")
        model_ids.add(model_id)
        if model.get("authority") is not False:
            errors.append(f"model authority must remain false at models[{index}]")
        if model.get("paid_token_required") is True:
            errors.append(f"paid-token model cannot enter zero-token registry at models[{index}]")
        if model.get("lifecycle_state") in RUNTIME_STATES:
            errors.append(f"runtime state is forbidden in metadata registry without runtime transition evidence at models[{index}]")
        for field in URL_FIELDS:
            if _unsafe_https_url(model.get(field)):
                errors.append(f"unsafe or invalid provenance URL at models[{index}].{field}")
        if model.get("artifact_url") is not None and _unsafe_https_url(model.get("artifact_url")):
            errors.append(f"unsafe or invalid artifact URL at models[{index}].artifact_url")
        for evidence_index, evidence in enumerate(model.get("source_evidence") or []):
            if _unsafe_https_url(evidence):
                errors.append(f"unsafe or invalid provenance URL at models[{index}].source_evidence[{evidence_index}]")
        errors.extend(_validate_e2e_candidate(model, index))

    forbidden = _forbidden_paths(document)
    if forbidden:
        errors.append(f"registry contains forbidden credential/secret or hardcoded enable data: {', '.join(forbidden[:8])}")
    return errors


def validate_open_model_universe(root: Path) -> list[str]:
    root = Path(root).resolve()
    schema_path = root / "AI_SKILL_LIBRARY/v4/schemas/open_model_universe.schema.json"
    registry_path = root / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
    errors: list[str] = []
    if not schema_path.is_file():
        errors.append(f"missing Open Model Universe schema: {schema_path.relative_to(root)}")
    if not registry_path.is_file():
        errors.append(f"missing Open Model Universe registry: {registry_path.relative_to(root)}")
    if errors:
        return errors
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [f"cannot load Open Model Universe contract: {exc}"]
    return validate_document(registry, schema)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Open Model Universe contracts")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    errors = validate_open_model_universe(Path(args.root))
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"OPEN_MODEL_UNIVERSE_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
