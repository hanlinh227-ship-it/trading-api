"""The AI CORE release gate: one verdict, read from evidence that already exists.

    python AI_SKILL_LIBRARY/v4/tools/ai_core_release_gate.py --evidence /tmp/gate.json

Each part of this lane produced its own proof, and each was checked in
isolation. Nothing checked them *together*, which is the state in which a lane
is most easily believed finished: every file says PASS, and no one has asked
whether they are all talking about the same artifact, the same runtime, or the
same week.

So this gate re-reads the recorded evidence and refuses on anything it cannot
establish. Three properties it enforces that no individual proof can:

**Every proof is about bytes something admitted.** Each recorded run must name
an artifact digest that is a registry row. The runs may legitimately differ - B1
proves a local model runs at all, the golden run uses whichever model the mesh
selected - but neither may rest on bytes nothing admitted, or inherit the other's
identity.

**Absent is not passing.** A missing evidence file, an unreadable one, or a
field that is not there fails the check it belongs to. This is the same rule the
admission boundary uses: a gate that did not run did not pass.

**Nothing in the lane may have granted itself authority.** The recorded runs
must all declare routing, memory, merge and approval authority false. A lane
that quietly acquired one would still report PASS on every other measure.

This gate observes. It cannot make a failing check pass, does not write to the
registry or the release pointer, and grants nothing: `PASS` means the evidence
holds, and cutting a release on it remains a human decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

EVIDENCE_DIR = "CHECKPOINTS/evidence"

#: The canonical control-plane chain. Order is part of the claim: a specialist
#: assigned after model selection is a label on a decision already taken.
CANONICAL_TRACE = [
    "ingress", "task_router", "task_decomposition", "ai_legion", "model_mesh",
    "runtime_scheduler", "wake_load", "real_inference", "verifier",
    "brain_synthesis", "response", "memory_update", "checkpoint", "warm_sleep",
]


class Missing:
    """Distinct from None, so an absent file is never read as a false value."""

    def __repr__(self) -> str:  # pragma: no cover - display only
        return "<missing>"


MISSING = Missing()


def _load(root: Path, name: str) -> Any:
    path = root / EVIDENCE_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MISSING


def _dig(document: Any, *keys: str) -> Any:
    current = document
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return MISSING
        current = current[key]
    return current


def _resolved_are_digest_bound(resolved: Any) -> bool:
    """Absent resolutions are fine; a resolution without a digest is not.

    `MISSING` is truthy, so the obvious `resolved or []` silently iterated the
    sentinel and raised. A sentinel that behaves like data is exactly what it
    exists to prevent, so it is type-checked rather than truth-tested.
    """
    if not isinstance(resolved, list):
        return False
    return all(
        isinstance(item, dict) and len(str(item.get("artifact_sha256") or "")) == 64
        for item in resolved
    )


def _check(name: str, requirement: str, *conditions: tuple[str, bool]) -> dict[str, Any]:
    failures = [reason for reason, held in conditions if not held]
    return {
        "check": name,
        "requirement": requirement,
        "passed": not failures,
        "failures": failures,
    }


#: Which document the golden checks judge, in order. The first that carries an
#: `ai_core_e2e` verdict wins; the second is a compatibility fallback for older
#: checkpoints.
#:
#: Named here, and reported in the result, because a fallback that silently
#: switches WHICH document is being judged is the shape this branch has been
#: bitten by repeatedly. It also made six refusal tests stop testing anything:
#: they damage a file, and the gate had quietly moved on to reading another one,
#: so the damage changed nothing and the gate passed. A check that cannot fail
#: is not a check. `golden_evidence_source` in the report lets a caller damage
#: the file the gate actually reads rather than the one it used to.
GOLDEN_EVIDENCE_PREFERENCE = (
    "B3_B4_GOLDEN_E2E_EVIDENCE.json",
    "AI_CORE_E2E_EVIDENCE.json",
)


def golden_evidence_source(root: Path) -> str:
    """The document the gate will judge for this tree."""
    first = _load(root, GOLDEN_EVIDENCE_PREFERENCE[0])
    if first is not MISSING and _dig(first, "ai_core_e2e") is not MISSING:
        return GOLDEN_EVIDENCE_PREFERENCE[0]
    return GOLDEN_EVIDENCE_PREFERENCE[1]


def gate(root: Path) -> dict[str, Any]:
    """Every check, with what it required and why it did or did not hold."""
    b1 = _load(root, "B1_REAL_INFERENCE_EVIDENCE.json")
    # The production Golden workflow writes B3_B4_GOLDEN_E2E_EVIDENCE.json.
    # Read the evidence generated by the current canonical run first; retain the
    # historical AI_CORE_E2E_EVIDENCE.json only as a compatibility fallback for
    # older checkpoints. This prevents a fresh semantic PASS from being rejected
    # because the release gate inspected stale pre-hardening evidence instead.
    e2e_source = GOLDEN_EVIDENCE_PREFERENCE[0]
    e2e = _load(root, e2e_source)
    if e2e is MISSING or _dig(e2e, "ai_core_e2e") is MISSING:
        e2e_source = GOLDEN_EVIDENCE_PREFERENCE[1]
        e2e = _load(root, e2e_source)
    resume = _load(root, "AI_CORE_RESUME_EVIDENCE.json")
    failure = _load(root, "FAILURE_PATH_PROOF.json")
    selfdev = _load(root, "SELFDEV_CYCLE_EVIDENCE.json")
    gaps = _load(root, "SELFDEV_OBSERVED_GAPS.json")

    import yaml

    try:
        registry = yaml.safe_load(
            (root / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml").read_text(encoding="utf-8")
        )
        models = [m for m in (registry.get("models") or []) if isinstance(m, dict)]
    except (OSError, ValueError, AttributeError):
        models = []

    checks: list[dict[str, Any]] = []

    # 1. A real local model really answered, offline, from verified bytes.
    checks.append(_check(
        "real_local_runtime",
        "B1 recorded a real generation from the cached artifact with egress denied",
        ("B1 evidence is absent or unreadable", b1 is not MISSING),
        ("b1_status is not PASS", _dig(b1, "b1_status") == "PASS"),
        ("the generation was not real", _dig(b1, "real_generation") is True),
        ("egress was not denied during the run", _dig(b1, "egress", "denied") is True),
        ("no runtime was named", bool(_dig(b1, "execution_evidence", "runtime_id"))),
        ("a fallback runtime was used", _dig(b1, "execution_evidence", "fallback_used") is False),
    ))

    # 2. The canonical chain ran end to end, in order, on a real model.
    trace = _dig(e2e, "trace")
    legion_before_mesh = (
        isinstance(trace, list)
        and "ai_legion" in trace and "model_mesh" in trace
        and trace.index("ai_legion") < trace.index("model_mesh")
    )

    semantic_pass = False
    semantic_failures: list[str] = []
    if e2e is not MISSING:
        try:
            from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import make_verifier
            semantic_report = make_verifier(str(_dig(e2e, "request")))(
                "core_reasoning",
                _dig(e2e, "runtime_evidence"),
            )
            semantic_pass = semantic_report.get("passed") is True
            semantic_failures = list(semantic_report.get("failures") or [])
        except Exception as exc:
            semantic_failures = [f"semantic_verifier_error:{type(exc).__name__}"]

    checks.append(_check(
        "golden_e2e",
        "the canonical trace ran in order with real inference and no failures",
        ("golden E2E evidence is absent or unreadable", e2e is not MISSING),
        ("ai_core_e2e is not PASS", _dig(e2e, "ai_core_e2e") == "PASS"),
        ("the trace is not the canonical chain", trace == CANONICAL_TRACE),
        ("AI Legion did not run before model selection", legion_before_mesh),
        ("the run reported failures", _dig(e2e, "failures") == []),
        ("inference was not real", _dig(e2e, "runtime_evidence", "real_inference") is True),
        ("the run was synthetic", _dig(e2e, "runtime_evidence", "synthetic") is False),
        ("the run was fixture-only", _dig(e2e, "runtime_evidence", "fixture_only") is False),
        ("the run was not offline", _dig(e2e, "runtime_evidence", "offline") is True),
        ("B2 did not pass", _dig(e2e, "B2_pass") is True),
        ("B3 did not pass", _dig(e2e, "B3_pass") is True),
        ("B4 did not pass", _dig(e2e, "B4_pass") is True),
        ("the recorded answer fails the canonical semantic verifier: " + ",".join(semantic_failures),
         semantic_pass),
    ))

    # 3. Work survived the process that did it. A resume inside the same process
    #    proves only that a dictionary is still in memory.
    different_process = (
        _dig(resume, "process_id") is not MISSING
        and _dig(e2e, "process_id") is not MISSING
        and _dig(resume, "process_id") != _dig(e2e, "process_id")
    )
    checks.append(_check(
        "memory_continuity",
        "a fresh process resumed the checkpoint the run wrote, granting no authority",
        ("resume evidence is absent or unreadable", resume is not MISSING),
        ("the state was not resumed", _dig(resume, "resume_status") == "RESUMED"),
        ("the resume happened in the same process", different_process),
        ("a different checkpoint was resumed",
         _dig(resume, "checkpoint_id") == _dig(e2e, "checkpoint", "checkpoint_id")),
        ("continuity was selected by something other than memory_continuity",
         _dig(resume, "selected_by") == "memory_continuity.select_continuation"),
        ("resuming granted memory authority", _dig(resume, "memory_authority") is False),
        ("resuming granted routing authority", _dig(resume, "routing_authority") is False),
    ))

    # 4. A refusal stays a refusal.
    checks.append(_check(
        "failure_paths",
        "every injected failure was refused and nothing was destroyed",
        ("failure-path proof is absent or unreadable", failure is not MISSING),
        ("failure paths are not proven", _dig(failure, "failure_paths") == "PROVEN"),
        ("not every case held", _dig(failure, "held") == _dig(failure, "cases")),
        ("something was destroyed", _dig(failure, "nothing_was_destroyed") is True),
        ("the canonical registry was written to",
         _dig(failure, "canonical_registry_untouched") is True),
    ))

    # 5. The machine has carried a real change, and refused a bad one.
    checks.append(_check(
        "self_development",
        "a bounded change reached READY_TO_MERGE on real gates and could not self-approve",
        ("self-development evidence is absent or unreadable", selfdev is not MISSING),
        ("the cycle is not proven", _dig(selfdev, "selfdev_cycle") == "PROVEN"),
        ("not every property held",
         _dig(selfdev, "properties_held") == _dig(selfdev, "properties_checked")),
        ("the run did not reach merge readiness",
         _dig(selfdev, "accepted_run", "final_state") == "AUTO_DEV_READY_TO_MERGE"),
        ("the automation was able to approve itself",
         _dig(selfdev, "accepted_run", "self_approval_refused") is True),
        ("a run could merge without approval",
         _dig(selfdev, "accepted_run", "can_merge_without_approval") is False),
        ("a rejected run could still be proposed",
         _dig(selfdev, "rejected_run", "rejected_run_can_still_propose") is False),
        ("the rollback was not verified against the base",
         _dig(selfdev, "rejected_run", "worktree_restored_to_base") is True),
    ))

    # 6. Nothing is outstanding that the observer could name.
    checks.append(_check(
        "no_open_gaps",
        "the observer reports no actionable gap, and every resolved one is digest-bound",
        ("observer output is absent or unreadable", gaps is not MISSING),
        ("actionable gaps remain", _dig(gaps, "gap_count") == 0),
        ("a resolved finding is not bound to an artifact digest",
         _resolved_are_digest_bound(_dig(gaps, "resolved"))),
        ("the observer claims it can act", _dig(gaps, "capabilities", "edits_registry") is False),
    ))

    # 7. Every admitted model earned it, and no row asserts two things at once.
    admitted = [m for m in models if m.get("model_mesh_local_candidate_eligible")]
    scanned_or_accepted = all(
        (m.get("admission_evidence") or {}).get("malware_scan_status") == "pass"
        or isinstance(m.get("operator_risk_acceptance"), dict)
        for m in admitted
    )
    # A passing scan beside a *live* acceptance is a row asserting that no scan
    # ran and that one did. A *superseded* acceptance is not that: it records a
    # decision taken before the scan existed, which the repository owner asked
    # to keep as history rather than delete. So the contradiction being checked
    # is two live claims, and a preserved one must say what replaced it.
    def _live_acceptance(model: dict) -> bool:
        acceptance = model.get("operator_risk_acceptance")
        if not isinstance(acceptance, dict):
            return False
        return not str(acceptance.get("superseded_by") or "").strip()

    never_both = all(
        not (
            (m.get("admission_evidence") or {}).get("malware_scan_status") == "pass"
            and _live_acceptance(m)
        )
        for m in models
    )
    supersession_named = all(
        str((m.get("artifact_identity") or {}).get("sha256") or "")
        in str((m.get("operator_risk_acceptance") or {}).get("superseded_by") or "")
        for m in models
        if isinstance(m.get("operator_risk_acceptance"), dict) and not _live_acceptance(m)
    )
    scan_bound = all(
        str((m.get("malware_scan_reference") or {}).get("artifact_sha256") or "")
        == str((m.get("artifact_identity") or {}).get("sha256") or "")
        for m in models if isinstance(m.get("malware_scan_reference"), dict)
    )
    checks.append(_check(
        "model_admission",
        "every mesh-eligible model holds a scan or a live acceptance, never both, bound to its own bytes",
        ("the registry could not be read", bool(models)),
        ("no model is mesh-eligible", bool(admitted)),
        ("a mesh-eligible model has neither a scan nor an acceptance", scanned_or_accepted),
        ("a row records a passing scan beside a live acceptance saying none ran", never_both),
        ("a superseded acceptance does not name the evidence that replaced it", supersession_named),
        ("a scan reference names bytes other than the row's own", scan_bound),
    ))

    # 8. Every run used bytes the registry actually tracks.
    #
    #    Not "one digest": B1 proves a local model runs at all, and the golden
    #    run uses whichever model the mesh selected, so they legitimately differ
    #    - B1 ran Qwen3-0.6B and the golden run ran the 4B. The requirement is
    #    that each names a real registry row, so no run can rest on bytes
    #    nothing admitted, or inherit another run's identity.
    #
    #    The two evidence writers spell the field differently (`artifact_sha256`
    #    against `sha256`), so both are read rather than one being assumed.
    def _digest(block: Any) -> Any:
        if not isinstance(block, dict):
            return MISSING
        for key in ("artifact_sha256", "sha256"):
            value = block.get(key)
            if isinstance(value, str) and value:
                return value.lower()
        return MISSING

    digests = {
        "b1": _digest(_dig(b1, "artifact_identity")),
        "golden_e2e": _digest(_dig(e2e, "runtime_evidence", "artifact_identity")),
    }
    present = {name: value for name, value in digests.items() if isinstance(value, str)}
    in_registry = {str((m.get("artifact_identity") or {}).get("sha256") or "").lower() for m in models}
    checks.append(_check(
        "runs_used_admitted_artifacts",
        "every recorded run names an artifact digest that is a registry row",
        ("a run recorded no artifact digest", len(present) == len(digests)),
        ("a run used bytes the registry does not track",
         bool(present) and set(present.values()) <= in_registry),
        ("a run's digest is not 64 hex characters",
         all(len(value) == 64 for value in present.values())),
    ))

    # 9. Authority ceilings, read from what the runs recorded about themselves.
    authority_claims = [
        ("golden E2E claimed routing authority", _dig(e2e, "legion", "orchestration_authority") is False),
        ("the checkpoint claimed memory authority", _dig(e2e, "checkpoint", "memory_authority") is False),
        ("the checkpoint claimed routing authority", _dig(e2e, "checkpoint", "routing_authority") is False),
        ("the self-development runner claimed merge authority",
         _dig(selfdev, "merge_authority") is False),
        ("the self-development runner claimed approval authority",
         _dig(selfdev, "approval_authority") is False),
        ("a self-development run recorded an approver",
         _dig(selfdev, "accepted_run", "run", "approved_by") is None),
    ]
    checks.append(_check(
        "authority_ceilings",
        "no recorded run claimed routing, memory, merge or approval authority",
        *authority_claims,
    ))

    failed = [row["check"] for row in checks if not row["passed"]]

    # Why the gate is red matters as much as that it is. A golden_e2e failure
    # whose only complaint is semantic is not broken code and not a bad gate:
    # it is recorded evidence that answers a question nobody asked any more,
    # and the only thing that can fix it is a real inference run producing a
    # real answer. Nothing in this repository can be edited to supply that, and
    # editing the recorded answer by hand is precisely what the check exists to
    # catch. So the verdict stays FAIL and the report says what would clear it.
    _SEMANTIC = ("semantic_answer_mismatch", "semantic_oracle_unavailable")
    _golden = next((c for c in checks if c["check"] == "golden_e2e"), None)
    _golden_semantic_only = bool(
        _golden and not _golden["passed"]
        and _golden["failures"]
        and all(any(term in str(f) for term in _SEMANTIC)
                for f in _golden["failures"]))
    regeneration_required = _golden_semantic_only and failed == ["golden_e2e"]
    return {
        "tool": "ai_core_release_gate",
        "gate": "AI_CORE_RELEASE",
        "verdict": "PASS" if not failed else "FAIL",
        # The three the integration directive asked CI to be able to report.
        # `release_eligible` is false whenever the verdict is not PASS - there
        # is no state in which this gate is red and a release may be cut.
        "release_eligible": not failed,
        # Which document the golden checks actually judged.
        "golden_evidence_source": e2e_source,
        "regeneration_required": regeneration_required,
        "evidence_class": "REAL_RUNTIME" if regeneration_required else None,
        "SEMANTIC_GOLDEN_VERIFIED": bool(_golden and _golden["passed"]),
        "operator_action": (
            "regenerate CHECKPOINTS/evidence/B3_B4_GOLDEN_E2E_EVIDENCE.json by "
            "running the canonical golden request on a host whose inference "
            "engine executes; do not edit the recorded answer"
            if regeneration_required else None),
        "checks_run": len(checks),
        "checks_passed": len(checks) - len(failed),
        "failed_checks": failed,
        "checks": checks,
        # Stated rather than implied: a gate that could grant anything would be
        # a second authority, and this lane is not allowed one.
        "grants_nothing": True,
        "release_authority": False,
        "routing_authority": False,
        "note": (
            "PASS means the recorded evidence holds together. Cutting a release remains "
            "a human decision; this gate reports and cannot approve."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    result = gate(Path(args.root).resolve())
    text = json.dumps(result, indent=2)
    if args.evidence:
        Path(args.evidence).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"AI_CORE_RELEASE={result['verdict']} "
          f"passed={result['checks_passed']}/{result['checks_run']}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
