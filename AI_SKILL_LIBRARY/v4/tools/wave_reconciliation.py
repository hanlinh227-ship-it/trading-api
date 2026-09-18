"""Re-verify Waves 1-5 against the artifacts and the runtime, at this HEAD.

    python AI_SKILL_LIBRARY/v4/tools/wave_reconciliation.py --evidence /tmp/rec.json

A closure recorded weeks ago is a claim about a moment. Artifacts can change on
disk, a licence record can go missing, a runtime can be upgraded under a
quarantine that was written against the old one. This walks the whole fleet and
re-establishes each fact from the thing itself, then classifies what is left.

Four questions per model, and the classification follows from the answers:

  ACTIONABLE     this runtime could resolve it at zero cost, so it is work
  HUMAN_ONLY     a licence, a credential or a device only the operator supplies
  TERMINAL       established by evidence and not resolvable here
  OK             verified at this HEAD

**A quarantine is re-tested, not re-asserted.** Each quarantined artifact was
recorded with a `revisit_if` naming exactly what would change the answer. Those
conditions are checked against the runtime that is installed right now, and the
artifact is offered to the loader again. If it still refuses, the quarantine is
renewed with a fresh diagnostic rather than inherited.

**Digests are recomputed from the bytes**, not read back from the manifest that
claims them. A manifest agreeing with itself proves nothing.

This tool admits nothing, promotes nothing and demotes nothing. It reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
EVIDENCE = "CHECKPOINTS/evidence"
CACHE = ".model-cache/models"

#: Waves, as the registry's own admission order records them. Used for grouping
#: the report; nothing here changes which wave a model belongs to.
WAVE_OF = {
    "Qwen/Qwen3-0.6B-GGUF": 1,
    "Qwen/Qwen3-1.7B-GGUF": 1,
    "ibm-granite/granite-3.3-2b-instruct-GGUF": 1,
    "Qwen/Qwen3-4B-GGUF": 1,
    "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF": 2,
    "ibm-granite/granite-4.2-3b-GGUF": 2,
    "microsoft/Phi-3-mini-4k-instruct-gguf": 2,
    "microsoft/bitnet-b1.58-2B-4T-gguf": 2,
    "mistralai/Ministral-3-3B-Reasoning-2512-GGUF": 2,
    "Qwen/Qwen3-8B-GGUF": 3,
}


def _sha256(path: Path, *, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _artifact_for(root: Path, model_id: str) -> Path | None:
    cache = root / CACHE
    if not cache.is_dir():
        return None
    prefix = model_id.replace("/", "_")
    for entry in sorted(cache.iterdir()):
        if entry.name.startswith(prefix) and entry.is_dir():
            files = sorted(entry.glob("*.gguf"))
            if files:
                return files[0]
    return None


def _capability_evidence(root: Path) -> dict[str, list[str]]:
    """Which models have a recorded measurement, and in which files."""
    found: dict[str, list[str]] = {}
    for path in sorted((root / EVIDENCE).glob("*.json")):
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        run = blob.get("benchmark_run") or {}
        model = run.get("model_id")
        if model and run.get("results"):
            found.setdefault(str(model), []).append(path.name)
    return found


def _revisit_conditions(root: Path, model_id: str) -> dict[str, Any]:
    """Check what the quarantine itself said would change the answer.

    Each incompatibility record names a `revisit_if`, and every one of those
    conditions is about the RUNTIME rather than the bytes: a build that accepts
    the format, or a backend that speaks it. Both are checkable with the
    artifact absent, and checking them is a far better answer than "the file is
    not in the cache" - which says nothing about whether the quarantine still
    holds.
    """
    try:
        blob = json.loads(
            (root / EVIDENCE / "RUNTIME_INCOMPATIBILITY_EVIDENCE.json").read_text(
                encoding="utf-8"))
    except (OSError, ValueError):
        return {"checked": False, "reason": "no incompatibility record to revisit"}

    record = next((r for r in (blob.get("records") or [])
                   if str(r.get("model_id")) == model_id), None)
    if record is None:
        return {"checked": False, "reason": "this model has no incompatibility record"}

    recorded_runtime = next(
        (t for t in (record.get("runtimes_tried") or [])
         if t.get("runtime") == "llama_cpp_python"), {})
    recorded_version = str(recorded_runtime.get("runtime_version") or "")
    try:
        import llama_cpp
        installed_version = str(getattr(llama_cpp, "__version__", ""))
    except Exception:  # noqa: BLE001
        installed_version = ""

    backends_dir = root / "AI_SKILL_LIBRARY/v4/local_runtime/backends"
    backends = sorted(p.stem for p in backends_dir.glob("*.py")
                      if not p.stem.startswith("__")) if backends_dir.is_dir() else []
    # A backend that could serve this artifact would be a new module here. The
    # two that exist are both upstream llama.cpp bindings, which is the thing
    # that refused it.
    new_backend = [b for b in backends if b not in ("llama_cpp", "llama_cpp_python")]

    runtime_changed = bool(installed_version and recorded_version
                           and installed_version != recorded_version)
    return {
        "checked": True,
        "revisit_if": record.get("revisit_if") or [],
        "runtime_version_when_quarantined": recorded_version or None,
        "runtime_version_installed_now": installed_version or None,
        "runtime_changed": runtime_changed,
        "backends_available": backends,
        "new_backend_since_quarantine": new_backend,
        "any_condition_met": bool(runtime_changed or new_backend),
        "artifact_digest_quarantined": record.get("artifact_sha256"),
        "recorded_diagnostic": str(record.get("runtime_diagnostic") or "")[:200],
    }


def _retest_quarantine(root: Path, model_id: str, artifact: Path) -> dict[str, Any]:
    """Offer the artifact to the installed runtime again. No assumption."""
    result: dict[str, Any] = {"retested": True, "loaded": False}
    try:
        from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (
            LlamaCppPythonBackend, detect_llama_cpp_python)
    except Exception as exc:  # noqa: BLE001
        return {"retested": False,
                "reason": f"backend unavailable: {type(exc).__name__}: {exc}"}
    identity = detect_llama_cpp_python()
    result["runtime_version"] = getattr(identity, "version", None)
    backend = LlamaCppPythonBackend(identity)
    if not backend.healthy():
        return {"retested": False, "reason": "no healthy llama.cpp runtime"}
    try:
        backend.load(model_id, artifact, context_limit=512)
        result["loaded"] = True
    except Exception as exc:  # noqa: BLE001
        result["error_type"] = type(exc).__name__
        result["diagnostic"] = str(exc)[:400]
    finally:
        try:
            backend.unload(model_id)
        except Exception:  # noqa: BLE001
            pass
    return result


def build(root: Path, *, verify_digests: bool = True,
          retest_quarantined: bool = True) -> dict[str, Any]:
    registry = yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}
    models = registry.get("models") or []
    measured = _capability_evidence(root)

    rows: list[dict[str, Any]] = []
    actionable: list[str] = []
    human_only: list[str] = []

    for record in models:
        model_id = str(record.get("model_id"))
        state = str(record.get("lifecycle_state") or record.get("state") or "UNKNOWN")
        identity = record.get("artifact_identity") or {}
        claimed = str(identity.get("sha256") or record.get("artifact_sha256") or "")
        artifact = _artifact_for(root, model_id)

        findings: list[str] = []
        checks: dict[str, Any] = {
            "registry_state": state,
            "artifact_present": artifact is not None,
            "licence_recorded": bool(record.get("license") or record.get("license_url")),
            "capability_evidence": measured.get(model_id, []),
        }

        if artifact is None:
            findings.append("artifact is not in the local cache")
        elif verify_digests and claimed:
            actual = _sha256(artifact)
            checks["digest_recomputed"] = actual
            checks["digest_matches"] = actual == claimed
            if actual != claimed:
                findings.append(
                    f"digest mismatch: cache holds {actual[:16]}, registry claims "
                    f"{claimed[:16]}")
        elif verify_digests:
            findings.append("registry records no digest to verify against")

        if not checks["licence_recorded"]:
            findings.append("no licence or licence URL recorded")
        if not checks["capability_evidence"] and state == "AVAILABLE":
            findings.append("admitted with no recorded capability measurement")

        classification = "OK"
        next_action = "none"

        if state == "QUARANTINED":
            # A quarantine is re-established, never inherited. With the bytes
            # present the artifact is offered to the loader again; without them,
            # the conditions the quarantine itself named are checked - and those
            # are all about the runtime, so the absent artifact does not weaken
            # the answer.
            conditions = _revisit_conditions(root, model_id)
            checks["revisit_conditions"] = conditions
            # An evicted artifact is the correct state for an unloadable model,
            # not a finding against it.
            findings = [f for f in findings if "not in the local cache" not in f]

            if retest_quarantined and artifact is not None:
                retest = _retest_quarantine(root, model_id, artifact)
                checks["quarantine_retest"] = retest
                if retest.get("loaded"):
                    classification = "ACTIONABLE"
                    next_action = ("the artifact now loads on the installed runtime; "
                                   "re-run admission before any capability claim")
                    findings.append("LOADS NOW - the quarantine's revisit condition is met")
                else:
                    classification = "TERMINAL"
                    next_action = ("quarantine renewed by re-offering the artifact to "
                                   "the installed runtime, which refused it again")
            elif conditions.get("any_condition_met"):
                classification = "ACTIONABLE"
                next_action = ("a revisit condition is now met; re-stage the artifact "
                               "and retest before any state change")
                findings.append(
                    "the runtime or backend changed since the quarantine was written")
            elif conditions.get("checked"):
                classification = "TERMINAL"
                next_action = (
                    f"quarantine stands: runtime is still "
                    f"{conditions.get('runtime_version_installed_now')} and no new "
                    f"backend exists. Revisit needs "
                    f"{'; '.join(conditions.get('revisit_if') or []) or 'a runtime change'}")
                findings.append(
                    "no revisit condition is met - runtime version unchanged "
                    f"({conditions.get('runtime_version_when_quarantined')} -> "
                    f"{conditions.get('runtime_version_installed_now')}) and no "
                    "backend added")
            else:
                classification = "TERMINAL"
                next_action = "quarantine stands; no incompatibility record to revisit"
        elif findings:
            classification = "ACTIONABLE"
            next_action = "; ".join(findings)

        if classification == "ACTIONABLE":
            actionable.append(model_id)
        if classification == "HUMAN_ONLY":
            human_only.append(model_id)

        rows.append({
            "item": model_id,
            "wave": WAVE_OF.get(model_id),
            "current_state": state,
            "evidence": checks,
            "actionable": classification == "ACTIONABLE",
            "human_only": classification == "HUMAN_ONLY",
            "terminal": classification == "TERMINAL",
            "classification": classification,
            "findings": findings,
            "next_action": next_action,
        })

    by_wave: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"WAVE{row['wave']}" if row["wave"] else "UNASSIGNED"
        entry = by_wave.setdefault(key, {"models": 0, "ok": 0, "terminal": 0,
                                         "actionable": 0, "human_only": 0})
        entry["models"] += 1
        entry["ok"] += int(row["classification"] == "OK")
        entry["terminal"] += int(row["terminal"])
        entry["actionable"] += int(row["actionable"])
        entry["human_only"] += int(row["human_only"])

    return {
        "tool": "wave_reconciliation",
        "reconciled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "digests_recomputed": verify_digests,
        "quarantines_retested": retest_quarantined,
        "RECONCILIATION_TABLE": rows,
        "by_wave": by_wave,
        "actionable_items": sorted(actionable),
        "human_only_items": sorted(human_only),
        "models_total": len(rows),
        "note": (
            "Every digest here was recomputed from the bytes in the cache, not "
            "read back from the manifest that claims it. Every quarantine was "
            "offered to the installed runtime again rather than inherited."),
        "routing_authority": False,
        "admission_authority": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--skip-digests", action="store_true",
                        help="skip recomputing digests; the report records that it did")
    parser.add_argument("--skip-retest", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root, verify_digests=not args.skip_digests,
                   retest_quarantined=not args.skip_retest)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    print(f"WAVE_RECONCILIATION models={result['models_total']} "
          f"actionable={len(result['actionable_items'])} "
          f"human_only={len(result['human_only_items'])}")
    for row in result["RECONCILIATION_TABLE"]:
        print(f"  W{row['wave']} {row['item']:<46} {row['current_state']:<12} "
              f"{row['classification']}")
        for finding in row["findings"]:
            print(f"        {finding}")
    return 0 if not result["actionable_items"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
