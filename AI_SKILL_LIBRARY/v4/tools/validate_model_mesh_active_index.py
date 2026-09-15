from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


FORBIDDEN_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer_token",
    "access_token",
    "private_key",
    "secret",
    "password",
    "credential",
)
SECRET_VALUE_RE = re.compile(r"(?:sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{8,}|hf_[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._~+/-]{8,})")


def _load(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _secret_findings(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            child = f"{path}.{key}"
            if any(marker in key_text for marker in FORBIDDEN_KEY_MARKERS):
                found.append(child)
            found.extend(_secret_findings(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_secret_findings(nested, f"{path}[{index}]"))
    elif isinstance(value, str) and SECRET_VALUE_RE.search(value):
        found.append(path)
    return found


def validate_active_index(
    root: Path,
    index_path: Path,
    *,
    snapshot_path: Path,
    expected_source_sha: str | None = None,
) -> list[str]:
    root = Path(root).resolve()
    index_path = Path(index_path)
    snapshot_path = Path(snapshot_path)
    if not index_path.is_absolute():
        index_path = root / index_path
    if not snapshot_path.is_absolute():
        snapshot_path = root / snapshot_path
    errors: list[str] = []

    try:
        index = _load(index_path)
        snapshot = _load(snapshot_path)
        schema = _load(root / "AI_SKILL_LIBRARY/v4/schemas/model_mesh_active_candidate_index.schema.json")
        capability_config = yaml.safe_load((root / "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return [str(exc)]

    Draft202012Validator.check_schema(schema)
    for error in sorted(Draft202012Validator(schema).iter_errors(index), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"schema {location}: {error.message}")

    if expected_source_sha is not None and index.get("source_sha") != expected_source_sha:
        errors.append(f"source_sha mismatch: expected={expected_source_sha} actual={index.get('source_sha')}")
    if index.get("source_sha") != snapshot.get("source_sha"):
        errors.append(f"source_sha mismatch with admitted snapshot: index={index.get('source_sha')} snapshot={snapshot.get('source_sha')}")
    if index.get("mode") != "FREE_ONLY":
        errors.append("active candidate index mode must be FREE_ONLY")
    if index.get("routing_authority") is not False or index.get("reasoning_authority") is not False:
        errors.append("active candidate index must have zero routing/reasoning authority")

    dimensions = set(str(item) for item in capability_config.get("dimensions", []))
    admitted = {
        (str(row.get("provider_id", "")), str(row.get("model_id", ""))): str(row.get("model_family", ""))
        for row in snapshot.get("models", [])
        if isinstance(row, dict)
    }
    seen_keys: set[str] = set()
    previous: tuple[str, str, str] | None = None
    for entry_index, entry in enumerate(index.get("entries", []) if isinstance(index.get("entries"), list) else []):
        if not isinstance(entry, dict):
            continue
        provider_id = str(entry.get("provider_id", ""))
        model_id = str(entry.get("model_id", ""))
        model_family = str(entry.get("model_family", ""))
        candidate_key = str(entry.get("candidate_key", ""))
        expected_key = f"{provider_id}:{model_id}"
        if candidate_key != expected_key:
            errors.append(f"entries[{entry_index}] candidate_key mismatch: expected={expected_key} actual={candidate_key}")
        if candidate_key in seen_keys:
            errors.append(f"duplicate candidate_key: {candidate_key}")
        seen_keys.add(candidate_key)
        admitted_family = admitted.get((provider_id, model_id))
        if admitted_family is None:
            errors.append(f"entries[{entry_index}] not present in admitted snapshot: {candidate_key}")
        elif admitted_family != model_family:
            errors.append(f"entries[{entry_index}] model_family mismatch for admitted snapshot: {candidate_key}")
        ordering = (provider_id, model_id, model_family)
        if previous is not None and ordering < previous:
            errors.append("active candidate index entries must be deterministically sorted by provider_id, model_id, model_family")
        previous = ordering
        cap_evidence = entry.get("capability_evidence", {})
        if isinstance(cap_evidence, dict):
            unknown = sorted(set(cap_evidence) - dimensions)
            if unknown:
                errors.append(f"entries[{entry_index}] contains unknown capability dimensions: {unknown}")

    if len(seen_keys) != len(admitted):
        missing = sorted(f"{provider}:{model}" for provider, model in admitted if f"{provider}:{model}" not in seen_keys)
        if missing:
            errors.append("active candidate index missing admitted snapshot models: " + ", ".join(missing[:10]))

    coverage = index.get("coverage", {})
    if isinstance(coverage, dict):
        previous_key: str | None = None
        for key, row in coverage.items():
            if previous_key is not None and key < previous_key:
                errors.append("coverage keys must be deterministically sorted")
                break
            previous_key = key
            if isinstance(row, dict):
                capability = str(row.get("capability", ""))
                if capability and capability not in dimensions:
                    errors.append(f"coverage {key} uses unknown capability dimension: {capability}")
                if row.get("enabled") is True and row.get("gate_eligible") is not True:
                    errors.append(f"coverage {key} enables hard gate without gate_eligible=true")

    secret_findings = _secret_findings(index)
    if secret_findings:
        errors.append("active candidate index contains forbidden secret material: " + ", ".join(secret_findings[:10]))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the bounded Model Mesh Active Candidate Index")
    parser.add_argument("index")
    parser.add_argument("--root", default=".")
    parser.add_argument("--snapshot", default="AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json")
    parser.add_argument("--source-sha", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    errors = validate_active_index(root, Path(args.index), snapshot_path=Path(args.snapshot), expected_source_sha=args.source_sha)
    for item in errors:
        print(f"[ERROR] {item}")
    print(f"MODEL_MESH_ACTIVE_INDEX_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
