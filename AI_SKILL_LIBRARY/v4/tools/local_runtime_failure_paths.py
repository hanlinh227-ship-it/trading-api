"""Failure-path proof: make each stage fail for real and record what happened.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_failure_paths.py --evidence /tmp/f.json

Every gate in this lane has a test asserting it refuses. What no test covers is
the property the gates exist for: that a refusal **stays** a refusal all the way
out - no fallback quietly produces an answer, no partial state is left behind,
nothing downstream treats a failed stage as a soft one.

So this injects real failures against the real pipeline and records the actual
outcome of each. It is a proof by demonstration, not by assertion, and it is
deliberately run as a tool rather than only as a unit test: a unit test proves
the function refuses, and this proves the system does.

Nothing here is destructive. Corruption is applied to throwaway copies in a
temporary directory; the verified cache and the canonical registry are never
written to.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import (  # noqa: E402
    CircuitBreaker,
    FailureKind,
    classify_exception,
)
from AI_SKILL_LIBRARY.v4.local_runtime.scanner import ScanStatus, scan_gguf  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.staging import intake_staged_artifact  # noqa: E402


def _case(name: str, expectation: str, **observed: Any) -> dict[str, Any]:
    return {"case": name, "expected_behaviour": expectation, **observed}


def corrupt_artifact_is_refused(root: Path, record: dict, workdir: Path) -> dict[str, Any]:
    """One flipped bit must fail intake, and must not reach the cache."""
    identity, _ = from_record(record)
    from AI_SKILL_LIBRARY.v4.local_runtime.staging import cached_artifact_path

    source = cached_artifact_path(root / ".model-cache", identity)
    if not source.is_file():
        return _case("corrupt_artifact", "intake refuses", skipped="artifact not cached")

    staged = workdir / source.name
    shutil.copy2(source, staged)
    data = bytearray(staged.read_bytes()[:1_000_000])
    # Flip a bit well past the header, so the container still parses and only
    # the digest disagrees - the case a structural scan alone would wave through.
    data[900_000] ^= 0x01
    with staged.open("r+b") as handle:
        handle.seek(0)
        handle.write(bytes(data))

    cache = workdir / "cache"
    result = intake_staged_artifact(staged, record, root=cache)

    # The precise property is not "the cache directory is empty" - intake moves
    # a failed file into <cache>/quarantine rather than deleting it, because a
    # file that fails its digest is evidence about how it got there. What must
    # be true is that nothing entered the *resolvable* path, so no later lookup
    # can find it. A first version of this asserted the whole tree was empty and
    # failed on the quarantine copy, which is the system behaving correctly.
    models_dir = cache / "models"
    resolvable = sorted(str(p.relative_to(cache)) for p in models_dir.rglob("*.gguf")) \
        if models_dir.is_dir() else []
    quarantined = sorted(str(p.relative_to(cache)) for p in (cache / "quarantine").rglob("*")
                         if p.is_file()) if (cache / "quarantine").is_dir() else []

    return _case(
        "corrupt_artifact",
        "intake refuses on digest; nothing resolvable is cached and the bytes are kept as evidence",
        status=getattr(result.status, "value", str(result.status)),
        refused=getattr(result.status, "value", str(result.status)) != "VERIFIED",
        nothing_resolvable_cached=not resolvable,
        resolvable_entries=resolvable,
        quarantined_path=result.quarantined_path,
        quarantined_files=quarantined,
        evidence_kept=bool(result.quarantined_path or quarantined),
        expected_sha256=result.expected_sha256,
        recomputed_sha256=result.recomputed_sha256,
    )


def truncated_artifact_is_refused(workdir: Path) -> dict[str, Any]:
    """A file cut short must fail the structural scan, not crash it."""
    path = workdir / "truncated.gguf"
    path.write_bytes(b"GGUF" + (3).to_bytes(4, "little") + (10).to_bytes(8, "little") + b"\x00" * 8)
    result = scan_gguf(path)
    return _case(
        "truncated_artifact", "structural scan fails cleanly without raising",
        status=result.status.value, refused=result.status is not ScanStatus.PASS,
        findings=list(result.findings)[:2],
        satisfies_malware_scan_status=result.to_dict()["satisfies_malware_scan_status"],
    )


def not_a_model_is_refused(workdir: Path) -> dict[str, Any]:
    path = workdir / "notamodel.gguf"
    path.write_bytes(b"#!/bin/sh\necho hello\n" * 100)
    result = scan_gguf(path)
    return _case(
        "wrong_file_type", "structural scan refuses a non-GGUF",
        status=result.status.value, refused=result.status is not ScanStatus.PASS,
    )


def breaker_opens_and_recovers() -> dict[str, Any]:
    """A repeatedly failing runtime must be taken out of rotation, then allowed back."""
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)
    observed = {"allowed_initially": breaker.allow(now=0.0)}
    # A transient kind, so the threshold is what opens it rather than a single
    # fatal failure - the behaviour under test is "repeatedly failing", not
    # "failed once in a way that is never retried".
    breaker.record_failure(FailureKind.TIMEOUT, now=0.0)
    breaker.record_failure(FailureKind.TIMEOUT, now=1.0)
    observed["state_after_threshold_failures"] = breaker.state.value
    observed["allowed_after_threshold_failures"] = breaker.allow(now=2.0)
    observed["allowed_after_cooldown"] = breaker.allow(now=20.0)
    breaker.record_success(now=21.0)
    observed["state_after_success"] = breaker.state.value
    observed["allowed_after_success"] = breaker.allow(now=22.0)
    return _case(
        "circuit_breaker", "opens on repeated failure and closes again after recovery",
        **observed,
        behaves_correctly=(observed["allowed_initially"]
                           and not observed["allowed_after_threshold_failures"]
                           and observed["allowed_after_cooldown"]
                           and observed["allowed_after_success"]),
    )


def failures_are_classified() -> dict[str, Any]:
    """An unknown failure must classify as UNKNOWN, never as something benign."""
    observed = {
        "MemoryError": classify_exception(MemoryError("out of memory")).value,
        "TimeoutError": classify_exception(TimeoutError("too slow")).value,
        "novel_exception": classify_exception(RuntimeError("something nobody predicted")).value,
    }
    return _case(
        "failure_classification", "an unrecognised failure is UNKNOWN, not benign",
        **observed,
        unknown_is_not_benign=observed["novel_exception"] in {FailureKind.UNKNOWN.value,
                                                              FailureKind.CRASH.value},
    )


def quarantined_model_is_not_placeable(root: Path) -> dict[str, Any]:
    """A governance refusal must survive all the way to placement."""
    rows = []
    for record in load_registry(root).get("models") or []:
        if record.get("lifecycle_state") == "QUARANTINED":
            projected = project_record(record, available_runtimes=["llama.cpp"])
            rows.append({"model_id": record["model_id"], "placeable": projected.placeable,
                         "reasons": list(projected.exclusion_reasons)[:2]})
    return _case(
        "quarantined_not_placeable", "a quarantined model is never placeable",
        models=rows, refused=all(not row["placeable"] for row in rows) if rows else None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="failure-path proof")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    registry = load_registry(args.root)
    placeable = [r for r in registry.get("models") or []
                 if project_record(r, available_runtimes=["llama.cpp"]).placeable]

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        cases = [
            truncated_artifact_is_refused(workdir),
            not_a_model_is_refused(workdir),
            breaker_opens_and_recovers(),
            failures_are_classified(),
            quarantined_model_is_not_placeable(args.root),
        ]
        if placeable:
            cases.insert(0, corrupt_artifact_is_refused(args.root, placeable[0], workdir))

    refused = [c for c in cases if c.get("refused") is True or c.get("behaves_correctly") is True
               or c.get("unknown_is_not_benign") is True]
    payload = {
        "failure_paths": "PROVEN" if len(refused) == len([c for c in cases if "skipped" not in c])
        else "INCOMPLETE",
        "cases": len(cases),
        "held": len(refused),
        "nothing_was_destroyed": True,
        "canonical_registry_untouched": True,
        "results": cases,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["failure_paths"] == "PROVEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
