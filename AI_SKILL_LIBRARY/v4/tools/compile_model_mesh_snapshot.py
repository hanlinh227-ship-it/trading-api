from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .model_mesh import eligible_free_candidate, normalize_candidate
except ImportError:
    from model_mesh import eligible_free_candidate, normalize_candidate

_PROVIDER_FIELDS = {
    "provider_class", "model_id", "model_family", "model_variant", "endpoint_family",
    "free_status", "free_verified_at", "quota_scope", "quota_dimensions", "reset_semantics",
    "capabilities", "context_window", "privacy_class", "data_training_allowed_by_provider",
    "retention_policy", "usage_terms", "health", "latency_ema_ms", "success_rate_ema",
    "quality_scores", "last_benchmark_at", "source_evidence",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _sanitize_candidate(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise TypeError("candidate must be an object")
    provider_id = str(raw.get("provider_id") or "").strip()
    observed_at = str(raw.get("observed_at") or "").strip()
    if not provider_id or not observed_at:
        raise ValueError("candidate provider_id and observed_at are required")
    safe = {key: raw.get(key) for key in _PROVIDER_FIELDS}
    return normalize_candidate(provider_id, safe, observed_at=observed_at)


def _benchmarked(candidate: dict) -> bool:
    if not candidate.get("last_benchmark_at"):
        return False
    quality = candidate.get("quality_scores")
    if not isinstance(quality, dict) or not quality:
        return False
    capabilities = candidate.get("capabilities")
    if not isinstance(capabilities, dict):
        return False
    for row in capabilities.values():
        if not isinstance(row, dict):
            continue
        if row.get("supported") is True and float(row.get("score") or 0.0) > 0.0:
            evidence = row.get("evidence")
            if isinstance(evidence, list) and any(str(item).strip() for item in evidence):
                return True
    return False


def _eligible(candidate: dict, *, promoted: bool = False) -> bool:
    if candidate.get("provider_class") not in {"F1", "F2", "F3"}:
        return False
    if not eligible_free_candidate(candidate, data_class="PUBLIC"):
        return False
    if not candidate.get("source_evidence"):
        return False
    if not promoted and not _benchmarked(candidate):
        return False
    return True


def _load_active(path: Path) -> list[dict]:
    registry = _load_json(path)
    if registry.get("version") != 1 or registry.get("mode") != "FREE_ONLY":
        raise ValueError("active model registry metadata invalid")
    if registry.get("routing_authority") is not False or registry.get("reasoning_authority") is not False:
        raise ValueError("active model registry must have zero routing/reasoning authority")
    rows = registry.get("models")
    if not isinstance(rows, list):
        raise ValueError("active model registry models must be an array")
    admitted: list[dict] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        try:
            candidate = _sanitize_candidate(raw)
        except (TypeError, ValueError):
            continue
        if _eligible(candidate, promoted=True):
            admitted.append(candidate)
    return admitted


def _load_quarantine(path: Path) -> list[dict]:
    report = _load_json(path)
    if report.get("state") != "quarantine":
        raise ValueError("model candidates must come from quarantine")
    if report.get("routing_authority") is not False or report.get("stable_mutation") is not False:
        raise ValueError("candidate report must have zero routing/stable authority")
    admitted: list[dict] = []
    for raw in report.get("candidates", []):
        if not isinstance(raw, dict):
            continue
        try:
            candidate = _sanitize_candidate(raw)
        except (TypeError, ValueError):
            continue
        if _eligible(candidate, promoted=False):
            admitted.append(candidate)
    return admitted


def compile_snapshot(
    root: Path,
    *,
    source_sha: str,
    candidates_path: Path | None = None,
    active_registry_path: Path | None = None,
    output: Path,
    generated_at: str | None = None,
) -> dict:
    root = Path(root).resolve()
    source_sha = str(source_sha).strip()
    if len(source_sha) < 7:
        raise ValueError("source_sha must identify the exact source revision")
    if bool(candidates_path) == bool(active_registry_path):
        raise ValueError("provide exactly one of candidates_path or active_registry_path")

    if active_registry_path is not None:
        active_path = Path(active_registry_path)
        if not active_path.is_absolute():
            active_path = root / active_path
        admitted = _load_active(active_path)
    else:
        candidates = Path(candidates_path)
        if not candidates.is_absolute():
            candidates = root / candidates
        admitted = _load_quarantine(candidates)

    admitted.sort(key=lambda row: (row["provider_id"], row["model_id"], row["model_family"]))
    snapshot = {
        "schema_version": 1,
        "source_sha": source_sha,
        "mode": "FREE_ONLY",
        "routing_authority": False,
        "reasoning_authority": False,
        "generated_at": generated_at or _now(),
        "models": admitted,
    }

    output = Path(output)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a sanitized last-known-good FREE_ONLY model mesh snapshot")
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--candidates", default=None)
    parser.add_argument("--active-registry", default=None)
    parser.add_argument("--output", default="AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    if bool(args.candidates) == bool(args.active_registry):
        parser.error("provide exactly one of --candidates or --active-registry")
    root = Path(args.root).resolve()
    output = Path(args.output)
    snapshot = compile_snapshot(
        root,
        source_sha=args.source_sha,
        candidates_path=Path(args.candidates) if args.candidates else None,
        active_registry_path=Path(args.active_registry) if args.active_registry else None,
        output=output,
        generated_at=args.generated_at,
    )
    print(f"MODEL_MESH_SNAPSHOT_COMPILE=PASS models={len(snapshot['models'])} source_sha={snapshot['source_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
