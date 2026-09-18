"""Can the runtime actually load this model? Admission's missing question.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_verify_load.py --evidence /tmp/load.json

Licence, provenance, digest, format safety and a signature scan can all pass on
a model this engine cannot execute. Two did: BitNet's GGUF carries tensor type
36, which this llama.cpp build has removed, and Ministral-3 declares
architecture `mistral3` with a vocabulary the loader rejects. Both files are
exactly the bytes they claim to be and neither can run.

So this asks the only question that settles it - it loads the model - and
records what the engine said. A failure here is not a corrupt artifact and must
not be reported as one: the distinction is "these bytes are wrong" versus "this
runtime cannot read these bytes", and only the second is fixable by a different
engine build.

It records; it does not demote. Changing a record's lifecycle state is
governance's act.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (  # noqa: E402
    LlamaCppPythonBackend,
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.staging import resolve_cached  # noqa: E402


def verify_load(record: dict, cache: Path, backend_identity) -> dict[str, Any]:
    identity, reasons = from_record(record)
    model_id = str(record.get("model_id"))
    if identity is None:
        return {"model_id": model_id, "loadable": None, "reason": "; ".join(reasons)}
    artifact = resolve_cached(cache, record, verify=True)
    if artifact is None:
        return {"model_id": model_id, "loadable": None,
                "reason": "no verified artifact cached; nothing to load"}

    backend = LlamaCppPythonBackend(backend_identity)
    # A small context: this asks whether the engine understands the file, not
    # whether the host can hold a full-length session.
    diagnostics = io.StringIO()
    try:
        with contextlib.redirect_stderr(diagnostics):
            backend.load(identity.model_id, artifact, context_limit=512,
                         quantization=identity.quantization)
    except Exception as exc:  # noqa: BLE001 - the engine's refusal is the answer
        text = diagnostics.getvalue()
        return {
            "model_id": model_id,
            "loadable": False,
            "artifact_sha256": identity.artifact_sha256,
            "runtime": backend_identity.backend_version,
            "error": f"{type(exc).__name__}: {exc}",
            # The engine's own words, which name the tensor type or architecture
            # it does not support. A paraphrase would lose exactly that.
            "engine_diagnostics": [line for line in text.splitlines()
                                   if "error" in line.lower() or "REMOVED" in line][-6:],
            "artifact_is_intact": True,
            "note": ("the bytes verified against their digest and passed the structural scan; "
                     "this runtime build cannot read them"),
        }
    backend.unload(identity.model_id)
    return {
        "model_id": model_id,
        "loadable": True,
        "artifact_sha256": identity.artifact_sha256,
        "runtime": backend_identity.backend_version,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="verify models load")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--cache", type=Path, default=repo_root / ".model-cache")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    backend_identity = detect_llama_cpp_python()
    if backend_identity is None:
        print(json.dumps({"load_verification": "REFUSED",
                          "reason": "no real llama.cpp runtime available"}, indent=2))
        return 1

    rows = [verify_load(record, args.cache, backend_identity)
            for record in load_registry(args.root).get("models") or []
            if not args.model_id or str(record.get("model_id")) == args.model_id]

    payload = {
        "load_verification": "RAN",
        "runtime": backend_identity.backend_version,
        "loadable": sum(1 for r in rows if r.get("loadable") is True),
        "not_loadable": sum(1 for r in rows if r.get("loadable") is False),
        "undetermined": sum(1 for r in rows if r.get("loadable") is None),
        "records_nothing_in_the_registry": True,
        "results": rows,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
