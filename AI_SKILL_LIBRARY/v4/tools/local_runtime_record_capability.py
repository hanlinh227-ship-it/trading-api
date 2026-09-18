"""Write a measured capability into the canonical registry record.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_record_capability.py \\
        --evidence CHECKPOINTS/evidence/WAVE0_CAPABILITY_QWEN3_1_7B.json --write

Separate from the benchmark runner on purpose. A harness that can both measure a
model and promote it on the strength of its own measurement is one bug away from
promoting its own model, so `local_runtime_wave0.py` prints and stops, and this
reads what it printed.

It refuses to write unless the evidence earns it:

* the run must be promotable - COMPLETE, no errored items. A score computed over
  the items that did not crash is not a score;
* the evidence's artifact digest must equal the digest in the registry record it
  is about, so a measurement can never be applied to another model's bytes;
* the record must already exist. This updates a capability; it does not admit.

The resulting record is then judged by the canonical validator's own rule, which
requires exactly this shape - so a write that slipped past these checks would
still be caught there.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"


def refusals(evidence: Mapping[str, Any], registry_text: str) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    run = evidence.get("benchmark_run") or {}
    identity = evidence.get("artifact_identity") or {}
    digest = str(identity.get("artifact_sha256") or "").lower()

    if not evidence.get("promotable"):
        problems.append(f"run is not promotable (status {run.get('run_status')})")
    if int(run.get("errors") or 0) != 0:
        problems.append("run had errored items; a partial run is not a score")
    if len(digest) != 64:
        problems.append("evidence carries no artifact digest")
    elif digest not in registry_text:
        problems.append("no registry record carries this artifact digest")

    return problems, {
        "model_id": identity.get("model_id"),
        "digest": digest,
        "capability": run.get("capability"),
        "score": run.get("score"),
        "benchmark_id": run.get("suite_id"),
        "benchmark_version": run.get("suite_version"),
        "suite_hash": run.get("suite_hash"),
        "attempted": run.get("attempted"),
        "passed": run.get("passed"),
        "errors": run.get("errors"),
        "measured_at": run.get("started_at"),
        "runtime": run.get("backend_version"),
    }


def patch_registry(text: str, facts: Mapping[str, Any], evidence_ref: str) -> str:
    """Replace the record's declared capability and append its evidence.

    Edited as text, surgically. A YAML round-trip reformats the whole canonical
    file and buries the change in a diff nobody can review.
    """
    digest = facts["digest"]
    marker = f"      sha256: {digest}"
    if marker not in text:
        raise ValueError("record not found by digest")

    # The record runs from the "  - model_id:" line before the digest to the
    # next one after it.
    at = text.index(marker)
    start = text.rindex("\n  - model_id:", 0, at) + 1
    nxt = text.find("\n  - model_id:", at)
    end = len(text) if nxt < 0 else nxt + 1
    record = text[start:end]

    capability = str(facts["capability"])
    score = facts["score"]
    record = re.sub(
        rf"(\n    capabilities:\n(?:      #[^\n]*\n)*      {re.escape(capability)}: )[0-9.]+",
        rf"\g<1>{score}",
        record,
        count=1,
    )
    record = re.sub(r"\n    benchmark_profile: unverified",
                    f"\n    benchmark_profile: {facts['benchmark_id']}@{facts['benchmark_version']}"
                    f"+{str(facts['suite_hash'])[:12]}", record, count=1)
    record = re.sub(r"\n    quality_class: unverified",
                    "\n    quality_class: locally_measured", record, count=1)

    block = (
        f"    capability_evidence:\n"
        f"      {capability}:\n"
        f"        score: {score}\n"
        f"        benchmark_id: {facts['benchmark_id']}\n"
        f"        benchmark_version: {facts['benchmark_version']}\n"
        f"        suite_hash: {facts['suite_hash']}\n"
        f"        is_public_benchmark: false\n"
        f"        attempted: {facts['attempted']}\n"
        f"        passed: {facts['passed']}\n"
        f"        errors: {facts['errors']}\n"
        f"        measured_at: '{facts['measured_at']}'\n"
        f"        artifact_sha256: {digest}\n"
        f"        runtime: {facts['runtime']}\n"
        f"        evidence_ref: {evidence_ref}\n"
    )
    if "\n    capability_evidence:\n" in record:
        raise ValueError("record already carries capability evidence")
    if not record.endswith("\n"):
        record += "\n"
    record += block
    return text[:start] + record + text[end:]


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="record a measured capability")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    registry_path = args.root / REGISTRY_REL
    text = registry_path.read_text(encoding="utf-8")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    problems, facts = refusals(evidence, text)

    result: dict[str, Any] = {"model_id": facts["model_id"], "score": facts["score"],
                              "refusals": problems, "written": False}
    if problems:
        print(json.dumps(result, indent=2))
        return 1

    if args.write:
        reference = str(args.evidence.relative_to(args.root)) if args.evidence.is_absolute() \
            else str(args.evidence)
        registry_path.write_text(patch_registry(text, facts, reference), encoding="utf-8")
        result["written"] = True
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
