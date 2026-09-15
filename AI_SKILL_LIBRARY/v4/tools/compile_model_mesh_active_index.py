from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from .capability_evidence import capability_evidence_state, index_evidence_records, load_capability_ledger
    from .validate_model_mesh_snapshot import validate_snapshot
except ImportError:
    from capability_evidence import capability_evidence_state, index_evidence_records, load_capability_ledger
    from validate_model_mesh_snapshot import validate_snapshot


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_SNAPSHOT = "AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json"
DEFAULT_LEDGER = "AI_SKILL_LIBRARY/v4/model_mesh/capability_evidence.json"
DEFAULT_CAPABILITIES = "AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml"
DEFAULT_OUTPUT = "AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path(root).resolve() / path


def _load_json(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _load_capabilities(path: Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("domain capability config must be a mapping")
    return data


def _hard_gate_config(config: dict) -> tuple[int, float, bool, dict[str, bool], int, float]:
    policy = config.get("policy") or {}
    evidence = config.get("capability_evidence") or {}
    hard_gate = evidence.get("hard_gate") or {}
    freshness = evidence.get("default_freshness_hours")
    min_verified = hard_gate.get("min_verified_candidates")
    min_ratio = hard_gate.get("min_coverage_ratio")
    default_enabled = hard_gate.get("default_enabled")
    overrides = hard_gate.get("overrides") or {}
    hard_weight = policy.get("hard_capability_weight_threshold")
    if isinstance(freshness, bool) or not isinstance(freshness, int) or freshness <= 0:
        raise ValueError("capability_evidence.default_freshness_hours must be a positive integer")
    if isinstance(min_verified, bool) or not isinstance(min_verified, int) or min_verified < 1:
        raise ValueError("capability_evidence.hard_gate.min_verified_candidates must be >= 1")
    if isinstance(min_ratio, bool) or not isinstance(min_ratio, (int, float)) or not 0 <= float(min_ratio) <= 1:
        raise ValueError("capability_evidence.hard_gate.min_coverage_ratio must be between 0 and 1")
    if not isinstance(default_enabled, bool):
        raise ValueError("capability_evidence.hard_gate.default_enabled must be boolean")
    if not isinstance(overrides, dict) or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in overrides.items()):
        raise ValueError("capability_evidence.hard_gate.overrides must map string keys to booleans")
    if isinstance(hard_weight, bool) or not isinstance(hard_weight, (int, float)) or not 0 <= float(hard_weight) <= 1:
        raise ValueError("policy.hard_capability_weight_threshold must be between 0 and 1")
    return freshness, float(min_ratio), default_enabled, dict(sorted(overrides.items())), min_verified, float(hard_weight)


def compile_active_index(
    root: Path,
    *,
    source_sha: str,
    snapshot_path: Path,
    ledger_path: Path,
    capabilities_path: Path,
    output: Path,
    generated_at: str | None = None,
) -> dict:
    root = Path(root).resolve()
    source_sha = str(source_sha or "").strip().lower()
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be an exact 40-character lowercase git SHA")

    snapshot_path = _resolve(root, snapshot_path)
    ledger_path = _resolve(root, ledger_path)
    capabilities_path = _resolve(root, capabilities_path)
    output = _resolve(root, output)

    snapshot = _load_json(snapshot_path)
    snapshot_errors = validate_snapshot(root, snapshot_path, expected_source_sha=source_sha)
    if snapshot_errors:
        raise ValueError("invalid model mesh snapshot: " + "; ".join(snapshot_errors[:8]))
    ledger = load_capability_ledger(root, ledger_path)
    evidence_map = index_evidence_records(ledger)
    config = _load_capabilities(capabilities_path)

    dimensions = [str(item) for item in config.get("dimensions", [])]
    if not dimensions or len(dimensions) != len(set(dimensions)):
        raise ValueError("domain capability dimensions must be non-empty and unique")
    domains = config.get("domains") or {}
    if not isinstance(domains, dict) or not domains:
        raise ValueError("domain capability config declares no domains")
    freshness, min_ratio, default_enabled, overrides, min_verified, hard_weight = _hard_gate_config(config)
    generated = generated_at or _now()

    entries: list[dict] = []
    for candidate in sorted(snapshot.get("models", []), key=lambda row: (str(row.get("provider_id", "")), str(row.get("model_id", "")), str(row.get("model_family", "")))):
        provider_id = str(candidate.get("provider_id", ""))
        model_id = str(candidate.get("model_id", ""))
        model_family = str(candidate.get("model_family", ""))
        capability_states = {
            capability: capability_evidence_state(
                candidate,
                capability,
                evidence_map,
                now=generated,
                freshness_hours=freshness,
            )
            for capability in sorted(dimensions)
        }
        entries.append(
            {
                "candidate_key": f"{provider_id}:{model_id}",
                "provider_id": provider_id,
                "model_id": model_id,
                "model_family": model_family,
                "capability_evidence": capability_states,
            }
        )

    coverage: dict[str, dict] = {}
    valid_override_keys: set[str] = set()
    for domain, domain_row in sorted(domains.items()):
        caps = domain_row.get("capabilities", {}) if isinstance(domain_row, dict) else {}
        if not isinstance(caps, dict):
            raise ValueError(f"domain capabilities must be a mapping: {domain}")
        for capability, weight_raw in sorted(caps.items()):
            if capability not in dimensions:
                raise ValueError(f"unknown capability dimension in domain {domain}: {capability}")
            try:
                weight = float(weight_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid capability weight for {domain}.{capability}") from exc
            if weight < hard_weight:
                continue
            key = f"{domain}.{capability}"
            valid_override_keys.add(key)
            eligible_candidates = len(entries)
            verified_candidates = sum(
                1
                for entry in entries
                if entry["capability_evidence"].get(capability, {}).get("state") == "VERIFIED"
            )
            ratio = 0.0 if eligible_candidates == 0 else round(verified_candidates / eligible_candidates, 6)
            requested = bool(overrides.get(key, default_enabled))
            gate_eligible = verified_candidates >= min_verified and ratio >= min_ratio
            if requested and not gate_eligible:
                raise ValueError(
                    "CAPABILITY_HARD_GATE_COVERAGE_INSUFFICIENT "
                    f"{key} verified={verified_candidates} eligible={eligible_candidates} coverage={ratio:.6f}"
                )
            coverage[key] = {
                "domain": str(domain),
                "capability": str(capability),
                "eligible_candidates": eligible_candidates,
                "verified_candidates": verified_candidates,
                "coverage_ratio": ratio,
                "requested_enabled": requested,
                "gate_eligible": gate_eligible,
                "enabled": bool(requested and gate_eligible),
            }

    unknown_overrides = sorted(set(overrides) - valid_override_keys)
    if unknown_overrides:
        raise ValueError("unknown hard-gate override keys: " + ", ".join(unknown_overrides))

    index = {
        "schema_version": 1,
        "source_sha": source_sha,
        "mode": "FREE_ONLY",
        "routing_authority": False,
        "reasoning_authority": False,
        "generated_at": generated,
        "hard_gate_policy": {
            "default_enabled": default_enabled,
            "min_verified_candidates": min_verified,
            "min_coverage_ratio": min_ratio,
            "overrides": overrides,
        },
        "coverage": coverage,
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile the bounded Model Mesh Active Candidate Index")
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--domain-capabilities", default=DEFAULT_CAPABILITIES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    index = compile_active_index(
        Path(args.root),
        source_sha=args.source_sha,
        snapshot_path=Path(args.snapshot),
        ledger_path=Path(args.ledger),
        capabilities_path=Path(args.domain_capabilities),
        output=Path(args.output),
        generated_at=args.generated_at,
    )
    enabled = sum(1 for row in index["coverage"].values() if row["enabled"])
    verified = sum(
        1
        for entry in index["entries"]
        for state in entry["capability_evidence"].values()
        if state["state"] == "VERIFIED"
    )
    print(f"MODEL_MESH_ACTIVE_INDEX_COMPILE=PASS entries={len(index['entries'])} verified={verified} enabled_hard_gates={enabled} source_sha={index['source_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
