"""Find the canonical artifact anywhere on disk, then run B1 end to end.

One command that needs no decisions. It walks the filesystem for a file that
*is* the canonical artifact - matched by exact size first, then by SHA-256 -
and when it finds one it runs intake and then the B1 path without stopping to
ask anything.

Matching is by content, not by name. A file called `Qwen3-0.6B-Q8_0.gguf` that
hashes to something else is not the artifact, and a file called `blob.dat` that
hashes correctly is. Size is checked first because it is one `stat` and rules
out almost everything; only exact-size candidates are ever hashed, so scanning a
large filesystem stays cheap.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py
    python AI_SKILL_LIBRARY/v4/tools/local_runtime_autorun.py --search /mnt /media

Finding nothing is a normal result and exits 3, so this is safe to re-run or
schedule. It never downloads and never relaxes a gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry
from AI_SKILL_LIBRARY.v4.local_runtime.staging import (
    intake_staged_artifact,
    resolve_cached,
    sha256_file,
)
from AI_SKILL_LIBRARY.v4.tools import local_runtime_b1

#: Where an operator would plausibly drop a file. Searched before anything else.
DEFAULT_SEARCH_ROOTS = ("/home", "/tmp", "/mnt", "/media", "/srv", "/data", "/opt", "/var/tmp")

#: Never descended into: either irrelevant or actively hostile to walking.
SKIP_DIRS = {
    "/proc", "/sys", "/dev", "/run", "/snap",
    "/usr/lib", "/usr/share", "/var/lib/docker", "/opt/pw-browsers",
}


def iter_candidates(roots: Sequence[str], size_bytes: int) -> Iterator[Path]:
    """Files whose size matches exactly. Cheap filter before any hashing."""
    seen: set[str] = set()
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            if any(dirpath == skip or dirpath.startswith(skip + "/") for skip in SKIP_DIRS):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if not d.startswith(".git")]
            for name in filenames:
                path = Path(dirpath) / name
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    if path.stat().st_size != size_bytes:
                        continue
                except OSError:
                    continue
                key = str(path.resolve())
                if key not in seen:
                    seen.add(key)
                    yield path


def find_artifact(roots: Sequence[str], size_bytes: int, sha256: str) -> tuple[Path | None, list[str]]:
    """The first file whose bytes are the artifact, plus near-misses seen."""
    near_misses: list[str] = []
    for candidate in iter_candidates(roots, size_bytes):
        try:
            digest = sha256_file(candidate)
        except OSError:
            continue
        if digest == sha256:
            return candidate, near_misses
        near_misses.append(f"{candidate}: size matched, sha256 {digest[:16]}… did not")
    return None, near_misses


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--search", nargs="*", default=None, help="extra roots to search")
    parser.add_argument("--prompt", default="The capital of France is")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cache = Path(args.cache_root).resolve() if args.cache_root else root / ".model-cache"

    registry = load_registry(root)
    models = [m for m in (registry.get("models") or []) if isinstance(m, Mapping)]
    record = (
        next((m for m in models if str(m.get("model_id")) == args.model_id), None)
        if args.model_id else (models[0] if len(models) == 1 else None)
    )
    if record is None:
        # A bare NO_RECORD was unactionable once the registry held more than one
        # model, which it has since Wave 1: the documented invocation with no
        # --model-id started returning a status naming neither the cause nor the
        # remedy. Say which ids are there and what to pass.
        available = [str(m.get("model_id")) for m in models]
        print(json.dumps({
            "status": "NO_RECORD",
            "reason": (
                f"--model-id {args.model_id!r} matched no registry record"
                if args.model_id else
                f"the registry holds {len(models)} models, so --model-id is required"
            ),
            "available_model_ids": available,
        }, indent=2))
        return 2

    identity, reasons = from_record(record)
    if identity is None or identity.artifact_size_bytes is None:
        print(json.dumps({"status": "NO_IDENTITY", "reasons": list(reasons)}, indent=2))
        return 2

    payload: dict[str, Any] = {
        "tool": "local_runtime_autorun",
        "artifact_identity": identity.to_dict(),
    }

    # Already cached and still verifying? Then there is nothing to find.
    cached = resolve_cached(cache, record, verify=True)
    if cached is None:
        roots = list(args.search or DEFAULT_SEARCH_ROOTS)
        found, near_misses = find_artifact(roots, identity.artifact_size_bytes, identity.artifact_sha256)
        payload["searched_roots"] = roots
        payload["near_misses"] = near_misses
        if found is None:
            payload["status"] = "ARTIFACT_NOT_PRESENT"
            payload["reason"] = (
                f"no file on disk matches size {identity.artifact_size_bytes} and sha256 "
                f"{identity.artifact_sha256}"
            )
            print(json.dumps(payload, indent=2))
            return 3
        payload["found_at"] = str(found)
        intake = intake_staged_artifact(found, record, root=cache)
        payload["intake"] = intake.to_dict()
        if not intake.verified:
            payload["status"] = "INTAKE_FAILED"
            print(json.dumps(payload, indent=2))
            return 1
        cached = Path(intake.cached_path)

    payload["cached_path"] = str(cached)
    payload["b1"] = local_runtime_b1.run(root, cache, args.prompt, args.max_tokens, args.model_id)
    payload["status"] = payload["b1"].get("b1_status")

    text = json.dumps(payload, indent=2)
    if args.evidence:
        Path(args.evidence).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.evidence}")
    print(text)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
