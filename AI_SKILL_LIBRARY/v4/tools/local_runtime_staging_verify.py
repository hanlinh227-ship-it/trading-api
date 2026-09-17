"""Verify downloaded staged artifacts against the transport manifest.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_staging_verify.py --evidence /tmp/v.json

Manifest-driven, so a new model is an entry in `staging_manifest.json` rather
than a new code path. It does three things and refuses to do a fourth:

1. reassembles multi-part assets, for models over the 2 GiB release cap;
2. recomputes size and SHA-256 from the bytes on disk;
3. runs the bounded, non-executing structural GGUF scan.

It does **not** admit anything. Verifying that bytes are the bytes they claim to
be and clearing a model to run are different questions owned by different
planes, and this answers only the first. In particular the structural scan says
`satisfies_malware_scan_status: false` about itself, because parsing a header is
not an antivirus verdict.

Reassembly is verified as a whole, never per part. A correct set of parts
concatenated in the wrong order produces a file whose parts all hash correctly
and whose total does not - so the total is what decides.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.scanner import ScanError, scan_gguf  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.staging import sha256_file  # noqa: E402

MANIFEST_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"
_CHUNK = 8 * 1024 * 1024


def reassemble(parts: Sequence[Path], destination: Path) -> None:
    """Concatenate parts in the order the manifest lists them."""
    with destination.open("wb") as out:
        for part in parts:
            with part.open("rb") as handle:
                while True:
                    block = handle.read(_CHUNK)
                    if not block:
                        break
                    out.write(block)


def verify_entry(entry: dict[str, Any], staging: Path) -> dict[str, Any]:
    name = str(entry["filename"])
    target = staging / name
    reassembled = False

    if entry.get("reassembly_required"):
        parts = [staging / part for part in entry["release_parts"]]
        missing = [p.name for p in parts if not p.is_file()]
        if missing and not target.is_file():
            return {"id": entry["id"], "verified": False, "reason": f"missing parts: {missing}"}
        if not target.is_file():
            reassemble(parts, target)
            reassembled = True

    if not target.is_file():
        return {"id": entry["id"], "verified": False, "reason": f"{name} not downloaded"}

    size = target.stat().st_size
    digest = sha256_file(target)
    expected_size = entry.get("size_bytes")
    expected_sha = str(entry["expected_sha256"]).lower()

    problems = []
    if expected_size is not None and size != int(expected_size):
        problems.append(f"size {size} != {expected_size}")
    if digest != expected_sha:
        problems.append(f"sha256 {digest} != {expected_sha}")

    row: dict[str, Any] = {
        "id": entry["id"],
        "family": entry.get("family"),
        "filename": name,
        "path": str(target),
        "reassembled_from_parts": reassembled or bool(entry.get("reassembly_required")),
        "size_bytes": size,
        "sha256": digest,
        "immutable_revision": entry.get("immutable_revision"),
        "revision_status": entry.get("revision_status"),
        "verified": not problems,
    }
    if problems:
        row["reason"] = "; ".join(problems)
        # Bytes that are not what they claim are never scanned or cached. A
        # structural pass on the wrong file is worse than no result.
        return row

    try:
        row["structural_scan"] = dict(scan_gguf(target).to_dict())
    except ScanError as exc:
        row["structural_scan"] = {"status": "ERROR", "findings": [str(exc)],
                                  "satisfies_malware_scan_status": False}
        row["verified"] = False
    else:
        # ScanStatus serialises lowercase. Comparing against "PASS" made every
        # clean scan look like a failure, which is the safe direction to get
        # wrong but still wrong.
        if str(row["structural_scan"]["status"]).lower() != "pass":
            row["verified"] = False
    return row


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="verify staged artifacts")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--staging", type=Path, default=repo_root / ".model-staging")
    parser.add_argument("--only", default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest = json.loads((args.root / MANIFEST_REL).read_text(encoding="utf-8"))
    entries = [e for e in manifest["entries"] if not args.only or e["id"] == args.only]
    rows = [verify_entry(entry, args.staging) for entry in entries]

    payload = {
        "staging_verify": "PASS" if rows and all(r["verified"] for r in rows) else "INCOMPLETE",
        "verified": sum(1 for r in rows if r["verified"]),
        "total": len(rows),
        # Restated so no downstream reader can mistake this for admission.
        "admits_nothing": True,
        "malware_scan_performed": False,
        "results": rows,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["staging_verify"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
