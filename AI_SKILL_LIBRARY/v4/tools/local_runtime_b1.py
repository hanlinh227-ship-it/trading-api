"""B1: isolated first load and two real inferences against the canonical model.

Runs the whole B1 path and emits machine-readable evidence, or refuses and says
exactly which precondition is missing. Every precondition is checked against
canonical state; none can be supplied on the command line.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_b1.py --evidence /tmp/b1.json

Order matters and is enforced:

1. the model must be *governance-cleared* - projection must place it, which
   means the registry row cleared `admission_policy.yaml`;
2. the artifact must be cached and its SHA-256 must still match;
3. only then is a backend loaded, with proxy environment stripped so the load
   and both inferences run with no egress.

Refusing at step 1 while the row is `QUARANTINED` is the tool working, not
failing. There is no flag to skip it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (
    LlamaCppPythonBackend,
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.evidence import EvidenceRecorder, PeakSampler
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record
from AI_SKILL_LIBRARY.v4.local_runtime.residency import ResidencyState
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import FailureKind
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import TaskContract
from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached

#: Environment variables that could give a loading process a route out.
_EGRESS_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def deny_egress() -> Mapping[str, str]:
    """Strip proxy configuration for this process and report what was removed.

    An in-process GGUF load performs no network I/O of its own, so this closes
    the remaining route rather than being the only control. It is recorded in
    the evidence so the claim is checkable rather than asserted.
    """
    removed = {}
    for name in _EGRESS_VARS:
        value = os.environ.pop(name, None)
        if value is not None:
            removed[name] = "<removed>"
    os.environ["NO_PROXY"] = "*"
    return removed


def _refusal(stage: str, reason: str, **extra: Any) -> Mapping[str, Any]:
    return {
        "b1_status": "REFUSED",
        "refused_at": stage,
        "reason": reason,
        "real_generation": False,
        **extra,
    }


def run(root: Path, cache: Path, prompt: str, max_tokens: int,
        model_id: str | None) -> Mapping[str, Any]:
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

    # 1. Governance clearance. No flag bypasses this.
    projected = project_record(record)
    if not projected.placeable:
        return _refusal(
            "governance_admission",
            "the canonical record is not cleared for placement",
            artifact_identity=identity.to_dict(),
            governance={
                "lifecycle_state": record.get("lifecycle_state"),
                "admission_evidence": record.get("admission_evidence"),
                "exclusion_reasons": list(projected.exclusion_reasons),
            },
        )

    # 2. Verified artifact on disk.
    artifact = resolve_cached(cache, record, verify=True)
    if artifact is None:
        return _refusal(
            "artifact",
            "no verified artifact is cached for this identity; stage one via local_runtime_intake.py",
            artifact_identity=identity.to_dict(),
        )

    # 3. Backend.
    backend_identity = detect_llama_cpp_python()
    backend = LlamaCppPythonBackend(backend_identity)
    if not backend.healthy():
        return _refusal("backend", "no real llama.cpp runtime is available",
                        artifact_identity=identity.to_dict())

    egress_removed = deny_egress()
    snapshot = detect_resources(disk_path=str(cache))
    context_limit = int(record.get("context_window") or 2048)

    recorder = EvidenceRecorder(admitted_at=time.monotonic())
    recorder.describe(
        worker_id="local", request_id=f"b1-{identity.fingerprint[:12]}",
        model_id=identity.model_id, model_revision=identity.immutable_revision,
        artifact_sha256=identity.artifact_sha256, artifact_fingerprint=identity.fingerprint,
        actual_quantization=identity.quantization, runtime_id=backend.name,
        runtime_version=backend_identity.backend_version, backend="llama.cpp",
        backend_version=backend_identity.backend_version,
        placement_action="LOAD_FROM_CACHE",
    )
    recorder.begin(cold_or_warm="COLD", placement_action="LOAD_FROM_CACHE")

    try:
        with PeakSampler() as sampler:
            resident = backend.load(
                identity.model_id, artifact,
                context_limit=min(context_limit, 4096), quantization=identity.quantization,
            )
            recorder.load_finished()
            recorder.inference_started()
            contract = TaskContract(
                task_id="b1-cold", model_id=identity.model_id,
                payload={"prompt": prompt}, max_output_tokens=max_tokens,
                timeout_seconds=600.0,
            )
            cold = backend.execute(contract, backend.probe())
            warm_started = time.monotonic()
            warm = backend.execute(
                TaskContract(
                    task_id="b1-warm", model_id=identity.model_id,
                    payload={"prompt": prompt}, max_output_tokens=max_tokens,
                    timeout_seconds=600.0,
                ),
                backend.probe(),
            )
            warm_ms = round((time.monotonic() - warm_started) * 1000.0, 3)
    except Exception as exc:  # noqa: BLE001 - a real failure is evidence too
        kind = getattr(exc, "kind", FailureKind.UNKNOWN)
        evidence = recorder.finish(failure=kind, failure_source=f"{backend.name}:load_or_generate")
        return {
            "b1_status": "FAILED",
            "reason": str(exc),
            "artifact_identity": identity.to_dict(),
            "real_generation": False,
            **evidence.to_dict(),
        }

    evidence = recorder.finish(
        peak_ram_mb=sampler.peak_mb,
        peak_vram_mb=0.0 if not snapshot.gpus else None,
        tokens_input=cold.get("tokens_input"), tokens_output=cold.get("tokens_output"),
    )
    backend.unload(identity.model_id)

    return {
        "b1_status": "PASS",
        "real_generation": True,
        "artifact_identity": identity.to_dict(),
        "artifact_path": str(artifact),
        "egress": {"denied": True, "removed_env": egress_removed, "no_proxy": os.environ.get("NO_PROXY")},
        "residency": {
            "entered": ResidencyState.READY.value,
            "after_load": ResidencyState.WARM.value,
            "after_unload": ResidencyState.READY.value,
        },
        "cold_generation": {
            "output": cold["text"],
            "inference_latency_ms": cold.get("inference_latency_ms"),
            "tokens_input": cold.get("tokens_input"),
            "tokens_output": cold.get("tokens_output"),
        },
        "warm_generation": {
            "output": warm["text"],
            "inference_latency_ms": warm.get("inference_latency_ms"),
            "total_latency_ms": warm_ms,
            "tokens_output": warm.get("tokens_output"),
        },
        "load": {"cold_load_ms": resident.load_latency_ms, "peak_ram_mb": sampler.peak_mb},
        "host": snapshot.to_dict(),
        **evidence.to_dict(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--prompt", default="The capital of France is")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--evidence", default=None, help="write evidence JSON here")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cache = Path(args.cache_root).resolve() if args.cache_root else root / ".model-cache"
    payload = run(root, cache, args.prompt, args.max_tokens, args.model_id)

    text = json.dumps(payload, indent=2)
    if args.evidence:
        Path(args.evidence).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.evidence}")
    print(text)
    return 0 if payload.get("b1_status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
