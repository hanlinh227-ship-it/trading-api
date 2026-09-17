"""Wave 0: measure a local model's capability against a frozen suite.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_wave0.py --evidence /tmp/wave0.json

This exists because B2 is blocked on a number that must not be invented. The
Model Mesh refuses the local candidate for declaring `text_reasoning: 0.0`, and
the only honest way to change that declaration is to run the model and count.

It borrows B1's preconditions unchanged - governance clearance, then a cached
artifact whose SHA-256 still matches, then a real backend, then egress denial -
because a capability measured against unverified bytes measures nothing. There
is no flag that skips any of them, and no flag that supplies a score.

The tool only *measures*. Writing the result anywhere canonical is a separate,
deliberate step: `--ledger-record` prints the evidence row and stops. A
benchmark harness that could also edit the registry it is benchmarking for is
one bug away from promoting its own model.

That separation is not only prudence here. `v4/model_mesh/capability_evidence.json`
is sealed by the active release manifest, so appending a measured row to it
makes the release fail verification - correctly. A benchmark result is not a
reason to mutate a sealed Brain release; the measurement belongs in the Open
Model Universe record's `capability_evidence`, which is the model governance
plane, and in `CHECKPOINTS/evidence/`. Landing a row in the mesh ledger is a
release cut, and a release cut is its own governed act.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (  # noqa: E402
    LlamaCppPythonBackend,
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.benchmark import (  # noqa: E402
    BENCHMARKS_DIR,
    BenchmarkError,
    load_suite,
    run_suite,
)
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import TaskContract  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools.local_runtime_b1 import deny_egress  # noqa: E402

DEFAULT_SUITE = BENCHMARKS_DIR / "local_core_reasoning_v1.json"

#: The mesh's own floor, read from its policy rather than restated here, so the
#: two can never drift apart. Imported lazily to keep this tool importable
#: without the mesh config present.
def mesh_capability_floor() -> float:
    from AI_SKILL_LIBRARY.v4.tools import model_mesh as mesh

    policy = (mesh._load_domain_capabilities() or {}).get("policy", {})
    return float(policy.get("hard_capability_min_score") or 0.35)


def _refusal(stage: str, reason: str, **extra: Any) -> Mapping[str, Any]:
    return {"wave0_status": "REFUSED", "refused_at": stage, "reason": reason,
            "measured": False, **extra}


def run(root: Path, cache: Path, suite_path: Path, model_id: str | None) -> Mapping[str, Any]:
    try:
        suite = load_suite(suite_path)
    except BenchmarkError as exc:
        return _refusal("suite", str(exc))

    registry = load_registry(root)
    models = [m for m in (registry.get("models") or []) if isinstance(m, Mapping)]
    record = (
        next((m for m in models if str(m.get("model_id")) == model_id), None)
        if model_id else (models[0] if len(models) == 1 else None)
    )
    if record is None:
        return _refusal("registry", "no matching canonical registry row")

    identity, identity_reasons = from_record(record)
    if identity is None:
        return _refusal("identity", "; ".join(identity_reasons))

    projected = project_record(record)
    if not projected.placeable:
        return _refusal(
            "governance_admission",
            "the canonical record is not cleared for placement",
            artifact_identity=identity.to_dict(),
            exclusion_reasons=list(projected.exclusion_reasons),
        )

    artifact = resolve_cached(cache, record, verify=True)
    if artifact is None:
        return _refusal("artifact", "no verified artifact is cached for this identity",
                        artifact_identity=identity.to_dict())

    backend_identity = detect_llama_cpp_python()
    backend = LlamaCppPythonBackend(backend_identity)
    if not backend.healthy():
        return _refusal("backend", "no real llama.cpp runtime is available",
                        artifact_identity=identity.to_dict())

    egress_removed = deny_egress()
    snapshot = detect_resources(disk_path=str(cache))
    context_limit = min(int(record.get("context_window") or 2048), 4096)
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    load_started = time.monotonic()
    try:
        backend.load(identity.model_id, artifact,
                     context_limit=context_limit, quantization=identity.quantization)
    except Exception as exc:  # noqa: BLE001
        return _refusal("load", f"{type(exc).__name__}: {exc}",
                        artifact_identity=identity.to_dict())
    load_ms = round((time.monotonic() - load_started) * 1000.0, 3)

    counter = {"n": 0}

    def generate(prompt: str, max_tokens: int, decoding: Mapping[str, Any]) -> str:
        counter["n"] += 1
        contract = TaskContract(
            task_id=f"wave0-{counter['n']:03d}",
            model_id=identity.model_id,
            payload={"prompt": prompt, **decoding},
            max_output_tokens=max_tokens,
            timeout_seconds=600.0,
        )
        return backend.execute(contract, backend.probe())["text"]

    try:
        run_result = run_suite(
            suite, generate,
            model_id=identity.model_id,
            artifact_sha256=identity.artifact_sha256,
            backend_version=backend_identity.backend_version,
            started_at=started_at,
        )
    finally:
        backend.unload(identity.model_id)

    floor = mesh_capability_floor()
    clears = run_result.promotable and run_result.score >= floor

    return {
        "wave0_status": "MEASURED" if run_result.promotable else "DEGRADED",
        "measured": True,
        "artifact_identity": identity.to_dict(),
        "artifact_path": str(artifact),
        "suite_path": str(suite_path),
        "mesh_capability_floor": floor,
        "clears_mesh_floor": clears,
        "promotable": run_result.promotable,
        "load_latency_ms": load_ms,
        "context_limit": context_limit,
        "host": {
            "gpus": len(snapshot.gpus),
            "ram_total_mb": snapshot.ram_total_mb,
            "ram_available_mb": snapshot.ram_available_mb,
            "cpu_logical": snapshot.cpu_logical,
        },
        "egress": {"denied": True, "removed_env": egress_removed},
        "benchmark_run": run_result.to_dict(),
    }


def ledger_record(result: Mapping[str, Any], *, source_sha: str) -> Mapping[str, Any]:
    """Shape the measurement as a canonical capability-evidence row.

    Printed, never written. `passed` is the mesh floor comparison and nothing
    softer, and `provenance` points at the evidence file so the row can be
    traced back to the raw generations that produced it.
    """
    run_block = result.get("benchmark_run") or {}
    identity = result.get("artifact_identity") or {}
    # Bound to the artifact digest AND the suite hash. A row identified only by
    # suite name would be reusable across different bytes, which is the whole
    # thing a capability ledger exists to prevent.
    digest = str(identity.get("artifact_sha256") or "")
    if not digest:
        raise BenchmarkError("cannot build a ledger row without an artifact digest")
    return {
        "evidence_id": f"{run_block.get('suite_id')}-{digest[:12]}-{str(run_block.get('suite_hash'))[:12]}",
        "provider_id": "local_runtime",
        "model_id": str(identity.get("model_id")),
        "model_family": str(identity.get("family") or "unknown"),
        "capability": str(run_block.get("capability")),
        "benchmark_id": str(run_block.get("suite_id")),
        "benchmark_version": f"{run_block.get('suite_version')}+{str(run_block.get('suite_hash'))[:12]}",
        "score": float(run_block.get("score") or 0.0),
        "threshold": float(result.get("mesh_capability_floor") or 0.0),
        "passed": bool(result.get("clears_mesh_floor")),
        "measured_at": str(run_block.get("started_at")),
        "source_sha": source_sha,
        "environment": {
            "protocol": "local_inprocess",
            "runtime": str(run_block.get("backend_version") or "unknown"),
        },
        "provenance": {
            "kind": "local_benchmark_run",
            "reference": "CHECKPOINTS/evidence/WAVE0_CAPABILITY_EVIDENCE.json",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wave 0 capability measurement")
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument("--root", type=Path, default=repo_root)
    # The cache root is the directory `staging` lays models out under, not
    # the repo root. Defaulting to the repo root makes every lookup miss.
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--ledger-record", action="store_true",
                        help="also print the canonical capability-ledger row")
    parser.add_argument("--source-sha", default="0" * 40)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run(args.root, args.cache, args.suite, args.model_id)
    if args.ledger_record and result.get("measured"):
        result = {**result, "ledger_record": ledger_record(result, source_sha=args.source_sha)}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("wave0_status") == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
