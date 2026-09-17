"""PERSONAL_AI_BASELINE_001: run the canonical 12 Wave 0 tasks for real.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_baseline.py --evidence /tmp/baseline.json

Composition, ingestion and the freeze all belong to `v4/control_plane/`:
wave0.json fixes the twelve tasks, benchmark.py decides whether the wave is
ready and what a frozen baseline contains. This runs them and hands the result
to those functions unchanged. Nothing here decides that the baseline is ready.

Each task is run twice under greedy decoding. `reproducible` in the canonical
report means the two runs agreed - it is a comparison, not a flag, so a model
that drifts between identical calls cannot contribute to a frozen baseline.

If fewer than twelve tasks pass their verifier, the wave is not ready and no
baseline is frozen. That is a real result about this model and is reported as
one; there is no flag to freeze anyway.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.control_plane.benchmark import (  # noqa: E402
    freeze_baseline,
    ingest_wave0,
    load_wave0,
)
from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (  # noqa: E402
    LlamaCppPythonBackend,
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.evidence import PeakSampler  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import deny_egress  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import TaskContract  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.wave0_baseline import (  # noqa: E402
    DECODING,
    Wave0Error,
    load_prompts,
    prompts_hash,
    verify,
)


def environment_fingerprint(identity, backend_version: str, context_limit: int) -> str:
    """Everything that would make two runs incomparable, in one digest."""
    body = json.dumps(
        {
            "artifact_sha256": identity.artifact_sha256,
            "quantization": identity.quantization,
            "runtime": "llama.cpp",
            "runtime_version": backend_version,
            "context_limit": context_limit,
            "decoding": dict(sorted(DECODING.items())),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]


def run(root: Path, cache: Path, model_id: str | None = None) -> dict[str, Any]:
    tasks = load_wave0(root)
    prompt_doc = load_prompts()
    prompts = prompt_doc["prompts"]
    missing = sorted({t["task_id"] for t in tasks} - set(prompts))
    if missing:
        raise Wave0Error(f"no prompt for canonical tasks: {missing}")

    registry = load_registry(root)
    record = selected_reason = None
    if model_id:
        record = next((m for m in registry.get("models") or []
                       if str(m.get("model_id")) == model_id), None)
        if record is None:
            return {"baseline_status": "REFUSED", "reason": f"no registry row for {model_id}"}
        if not project_record(record, available_runtimes=["llama.cpp"]).placeable:
            return {"baseline_status": "REFUSED", "reason": f"{model_id} is not cleared for placement"}
        selected_reason = "explicitly requested"
    else:
        # Pick by measured capability, not by registry order. Taking the first
        # admitted row made the baseline depend on where a model happened to be
        # written down, which is how the weakest admitted model ends up being
        # the one the baseline is frozen against.
        #
        # A capability only counts when its evidence names this record's own
        # digest, so an unmeasured model cannot win by declaring a number.
        ranked = []
        for candidate in registry.get("models") or []:
            if not project_record(candidate, available_runtimes=["llama.cpp"]).placeable:
                continue
            digest = str((candidate.get("artifact_identity") or {}).get("sha256") or "")
            evidence = (candidate.get("capability_evidence") or {}).get("text_reasoning") or {}
            if str(evidence.get("artifact_sha256") or "") != digest or not digest:
                continue
            ranked.append((float(evidence.get("score") or 0.0), candidate))
        if not ranked:
            return {"baseline_status": "REFUSED",
                    "reason": "no governance-admitted local model carries a measured capability"}
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        record = ranked[0][1]
        selected_reason = (f"highest measured capability {ranked[0][0]} of "
                           f"{len(ranked)} admitted and measured models")

    identity, reasons = from_record(record)
    if identity is None:
        return {"baseline_status": "REFUSED", "reason": "; ".join(reasons)}
    artifact = resolve_cached(cache, record, verify=True)
    if artifact is None:
        return {"baseline_status": "REFUSED", "reason": "no verified artifact cached"}

    backend_identity = detect_llama_cpp_python()
    backend = LlamaCppPythonBackend(backend_identity)
    if not backend.healthy():
        return {"baseline_status": "REFUSED", "reason": "no real llama.cpp runtime available"}

    deny_egress()
    context_limit = min(int(record.get("context_window") or 2048), 4096)
    fingerprint = environment_fingerprint(identity, backend_identity.backend_version, context_limit)

    cold_started = time.monotonic()
    with PeakSampler() as sampler:
        backend.load(identity.model_id, artifact,
                     context_limit=context_limit, quantization=identity.quantization)
    load_ms = round((time.monotonic() - cold_started) * 1000.0, 3)

    def generate(task_id: str, prompt: str, max_tokens: int) -> dict[str, Any]:
        started = time.monotonic()
        result = backend.execute(
            TaskContract(task_id=task_id, model_id=identity.model_id,
                         payload={"prompt": prompt, **DECODING},
                         max_output_tokens=max_tokens, timeout_seconds=600.0),
            backend.probe(),
        )
        return {"text": result["text"],
                "latency_ms": round((time.monotonic() - started) * 1000.0, 3),
                "tokens_output": result.get("tokens_output")}

    runs: list[dict[str, Any]] = []
    try:
        for task in tasks:
            task_id = task["task_id"]
            spec = prompts[task_id]
            first = generate(task_id, spec["prompt"], int(spec.get("max_tokens") or 24))
            second = generate(f"{task_id}-repeat", spec["prompt"], int(spec.get("max_tokens") or 24))
            # Reproducible means the two runs agreed. Under greedy decoding a
            # disagreement is a real instability, not sampling noise.
            reproducible = first["text"] == second["text"]
            verdict = verify(task["category"], spec["expectation"], first["text"])
            runs.append({
                "task_id": task_id,
                "category": task["category"],
                "model_id": identity.model_id,
                "family": identity.family,
                "revision": identity.immutable_revision,
                "artifact_hash": identity.artifact_sha256,
                "quantization": identity.quantization,
                "runtime": "llama.cpp",
                "runtime_version": backend_identity.backend_version,
                "environment_fingerprint": fingerprint,
                "prompt_version": prompt_doc["prompt_version"],
                "benchmark_version": prompt_doc["benchmark_version"],
                "real_inference": True,
                "reproducible": reproducible,
                "verifier": task["verifier"],
                "verifier_passed": verdict["passed"],
                "failure": None if verdict["passed"] else {"verifier_failures": verdict["failures"]},
                "raw_run_ref": f"{identity.fingerprint}:{fingerprint}:{task_id}",
                "output": first["text"],
                "repeat_output": second["text"],
                "cold_metrics": {"load_latency_ms": load_ms,
                                 "inference_latency_ms": first["latency_ms"],
                                 "peak_ram_mb": sampler.peak_mb},
                "warm_metrics": {"inference_latency_ms": second["latency_ms"],
                                 "tokens_output": second["tokens_output"]},
            })
    finally:
        backend.unload(identity.model_id)

    report = ingest_wave0(tasks, runs)
    payload: dict[str, Any] = {
        "baseline_status": "READY" if report["ready_to_freeze"] else "NOT_READY",
        "model_id": identity.model_id,
        "model_selected_because": selected_reason,
        "prompts_hash": prompts_hash(prompt_doc),
        "environment_fingerprint": fingerprint,
        "passed": sum(1 for r in runs if r["verifier_passed"]),
        "reproducible": sum(1 for r in runs if r["reproducible"]),
        "total": len(runs),
        "wave_report": report,
    }
    if report["ready_to_freeze"]:
        payload["baseline"] = freeze_baseline(report)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Wave 0 baseline")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--model-id", default=None,
                        help="force a model; default is the highest measured capability")
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run(args.root, args.cache, args.model_id)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("baseline_status") == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
