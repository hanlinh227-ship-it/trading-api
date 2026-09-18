"""Measure cold load, warm reuse and resident cost for every admitted model.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_residency_profile.py --evidence /tmp/r.json

The design spec found that cold load dominates first-response latency and that
the mesh's `latency_efficiency` term contributes nothing because
`latency_ema_ms` was never populated. This produces the numbers that term needs,
measured rather than estimated.

Each model is loaded cold, asked the same short prompt twice, and unloaded. What
the two calls separate is the thing that actually matters for residency: the
second pays no load, so `cold_total` minus `warm_inference` is what keeping the
model resident would save on the next request.

Every model is measured on the same prompt and token budget, because a latency
comparison between models answering different questions is not a comparison.
Nothing here writes to the registry or changes selection - it measures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (  # noqa: E402
    LlamaCppPythonBackend,
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.evidence import PeakSampler  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import deny_egress  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.runtime import TaskContract  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached  # noqa: E402

#: One prompt for every model. Comparing latencies across different prompts
#: would measure the prompts.
PROMPT = "The capital of France is"
MAX_TOKENS = 24
DECODING = {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "seed": 0, "reset_state": True}


def drop_page_cache() -> bool:
    """Evict the page cache so a "cold" load is actually cold.

    Without this the first measurement is really "load from page cache", and it
    varies by whatever was read last rather than by the model. That showed up
    immediately: Granite measured a 618 ms cold load against Qwen3-1.7B's
    4212 ms for a *smaller* file, purely because Granite's bytes were still
    cached from an earlier run. Reporting those as cold-load figures would have
    made a cache artefact look like a property of the model.

    Requires privilege. Returns whether it worked, so a profile taken without it
    says so instead of quietly claiming numbers it did not earn.
    """
    try:
        os.sync()
        Path("/proc/sys/vm/drop_caches").write_text("3\n", encoding="utf-8")
        return True
    except (OSError, PermissionError):
        return False


def profile_model(record: dict, cache: Path, backend_identity, *,
                  cold: bool = True) -> dict[str, Any]:
    identity, reasons = from_record(record)
    if identity is None:
        return {"model_id": record.get("model_id"), "measured": False, "reason": "; ".join(reasons)}
    artifact = resolve_cached(cache, record, verify=True)
    if artifact is None:
        return {"model_id": identity.model_id, "measured": False,
                "reason": "no verified artifact cached"}

    backend = LlamaCppPythonBackend(backend_identity)
    context_limit = min(int(record.get("context_window") or 2048), 4096)

    page_cache_dropped = drop_page_cache() if cold else False

    started = time.monotonic()
    with PeakSampler() as sampler:
        backend.load(identity.model_id, artifact,
                     context_limit=context_limit, quantization=identity.quantization)
        load_ms = round((time.monotonic() - started) * 1000.0, 3)

        def generate(task_id: str) -> float:
            at = time.monotonic()
            backend.execute(
                TaskContract(task_id=task_id, model_id=identity.model_id,
                             payload={"prompt": PROMPT, **DECODING},
                             max_output_tokens=MAX_TOKENS, timeout_seconds=600.0),
                backend.probe(),
            )
            return round((time.monotonic() - at) * 1000.0, 3)

        cold_inference = generate("cold")
        warm_inference = generate("warm")
    backend.unload(identity.model_id)

    capability = (record.get("capability_evidence") or {}).get("text_reasoning") or {}
    return {
        "model_id": identity.model_id,
        "measured": True,
        "quantization": identity.quantization,
        "artifact_size_bytes": identity.artifact_size_bytes,
        "context_limit": context_limit,
        "page_cache_dropped_before_load": page_cache_dropped,
        "cold_load_ms": load_ms,
        "cold_inference_ms": cold_inference,
        "cold_total_ms": round(load_ms + cold_inference, 3),
        "warm_inference_ms": warm_inference,
        # What residency actually buys on the next request.
        "residency_saving_ms": round(load_ms + cold_inference - warm_inference, 3),
        "peak_ram_mb": sampler.peak_mb,
        "measured_capability": capability.get("score"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="residency and latency profile")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--no-drop-caches", action="store_true",
                        help="do not evict the page cache; cold figures are then not cold")
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    backend_identity = detect_llama_cpp_python()
    if backend_identity is None:
        print(json.dumps({"residency_profile": "REFUSED",
                          "reason": "no real llama.cpp runtime available"}, indent=2))
        return 1

    deny_egress()
    snapshot = detect_resources(disk_path=str(args.cache))
    registry = load_registry(args.root)
    rows = [profile_model(record, args.cache, backend_identity, cold=not args.no_drop_caches)
            for record in registry.get("models") or []
            if project_record(record, available_runtimes=["llama.cpp"]).placeable]

    measured = [r for r in rows if r.get("measured")]
    payload = {
        "residency_profile": "MEASURED" if measured else "EMPTY",
        "prompt": PROMPT,
        "max_tokens": MAX_TOKENS,
        "decoding": "greedy, state reset before each call",
        "cold_loads_are_page_cache_cold": all(
            r.get("page_cache_dropped_before_load") for r in rows if r.get("measured")
        ),
        "runtime": backend_identity.backend_version,
        "host_ram_total_mb": snapshot.ram_total_mb,
        "host_gpus": len(snapshot.gpus),
        "models": rows,
        # Restated: this measures, it does not change routing or the registry.
        "changes_nothing": True,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if measured else 1


if __name__ == "__main__":
    raise SystemExit(main())
