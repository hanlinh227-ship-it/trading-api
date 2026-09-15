from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

try:
    from .model_mesh import eligible_free_candidate
except ImportError:
    from model_mesh import eligible_free_candidate

FORBIDDEN_KEY_MARKERS = (
    "api_key", "apikey", "authorization", "bearer_token", "access_token", "private_key", "secret", "password", "credential",
)


def _load(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError(f"JSON root must be an object: {path}")
    return data


def _validator(root: Path) -> Draft202012Validator:
    snapshot_schema = _load(root / "AI_SKILL_LIBRARY/v4/schemas/model_mesh_snapshot.schema.json")
    provider_schema = _load(root / "AI_SKILL_LIBRARY/v4/schemas/model_mesh_provider.schema.json")
    schema = deepcopy(snapshot_schema);schema["properties"]["models"]["items"] = provider_schema
    Draft202012Validator.check_schema(schema);return Draft202012Validator(schema)


def _secret_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower();child = f"{path}.{key}"
            if any(marker in key_text for marker in FORBIDDEN_KEY_MARKERS): found.append(child)
            found.extend(_secret_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value): found.extend(_secret_paths(nested, f"{path}[{index}]"))
    return found


def _benchmarked(candidate: dict) -> bool:
    if not candidate.get("last_benchmark_at"): return False
    scores = candidate.get("quality_scores")
    if not isinstance(scores, dict) or not scores: return False
    capabilities = candidate.get("capabilities")
    if not isinstance(capabilities, dict): return False
    return any(isinstance(row, dict) and row.get("supported") is True and float(row.get("score") or 0.0) > 0.0 and isinstance(row.get("evidence"), list) and any(str(item).strip() for item in row["evidence"]) for row in capabilities.values())


def validate_snapshot(root: Path, snapshot_path: Path, *, expected_source_sha: str | None = None) -> list[str]:
    root = Path(root).resolve();errors: list[str] = []
    try: snapshot = _load(Path(snapshot_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc: return [str(exc)]
    for error in sorted(_validator(root).iter_errors(snapshot), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$";errors.append(f"schema {location}: {error.message}")
    if expected_source_sha is not None and snapshot.get("source_sha") != expected_source_sha: errors.append(f"source_sha mismatch: expected={expected_source_sha} actual={snapshot.get('source_sha')}")
    if snapshot.get("mode") != "FREE_ONLY": errors.append("snapshot mode must be FREE_ONLY")
    if snapshot.get("routing_authority") is not False or snapshot.get("reasoning_authority") is not False: errors.append("model mesh snapshot must have zero routing/reasoning authority")
    secret_paths = _secret_paths(snapshot)
    if secret_paths: errors.append("snapshot contains forbidden secret-like fields: " + ", ".join(secret_paths[:10]))
    models = snapshot.get("models", [])
    if isinstance(models, list):
        seen: set[tuple[str, str]] = set();previous: tuple[str, str, str] | None = None
        for index, candidate in enumerate(models):
            if not isinstance(candidate, dict): continue
            key=(str(candidate.get("provider_id") or ""),str(candidate.get("model_id") or ""))
            if key in seen: errors.append(f"duplicate provider/model path at models[{index}]: {key[0]}:{key[1]}")
            seen.add(key);ordering=(key[0],key[1],str(candidate.get("model_family") or ""))
            if previous is not None and ordering < previous: errors.append("snapshot models must be deterministically sorted by provider_id, model_id, model_family");break
            previous=ordering
            if candidate.get("provider_class") not in {"F1","F2","F3"}: errors.append(f"models[{index}] provider_class is not active free capacity")
            if not eligible_free_candidate(candidate,data_class="PUBLIC"): errors.append(f"models[{index}] violates FREE_ONLY eligibility")
            if not candidate.get("source_evidence"): errors.append(f"models[{index}] missing source evidence")
            # A manually promoted model may enter as degraded before its first live canary.
            # Only healthy claims require measured benchmark evidence; degraded is honest pre-canary state.
            if candidate.get("health")=="healthy" and not _benchmarked(candidate): errors.append(f"models[{index}] claims healthy without benchmark evidence")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Validate sanitized Adaptive Free Model Mesh snapshot");parser.add_argument("snapshot");parser.add_argument("--root",default=".");parser.add_argument("--source-sha",default=None);args=parser.parse_args()
    root=Path(args.root).resolve();snapshot=Path(args.snapshot)
    if not snapshot.is_absolute(): snapshot=root/snapshot
    errors=validate_snapshot(root,snapshot,expected_source_sha=args.source_sha)
    for item in errors: print(f"[ERROR] {item}")
    print(f"MODEL_MESH_SNAPSHOT_VALIDATE={'PASS' if not errors else 'FAIL'} errors={len(errors)}");return 1 if errors else 0


if __name__ == "__main__": raise SystemExit(main())
