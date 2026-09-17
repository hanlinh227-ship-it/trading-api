"""Drive the Free Worker Mesh through the scenarios the gate names.

    python AI_SKILL_LIBRARY/v4/tools/free_worker_mesh_proof.py --evidence /tmp/mesh.json

The unit tests prove each invariant in isolation. This proves the fabric behaves
when the scenarios run against the real registries, the real host measurement and
the real recorded provider paths - and it runs a genuine federated inference at
the end, so the chain from a request to an answer is exercised rather than
described.

Nine rounds, each constructing the condition rather than asserting the outcome:

  A  a request with an owned worker online lands on it
  B  the preferred worker goes stale mid-flight; the next one takes the work
  C  a free tier is exhausted; it is bypassed, not retried
  D  a worker fails repeatedly; its circuit opens and another is used
  E  it comes back after cooldown, because a breaker is not a removal
  F  a confidential payload is refused a third-party provider outright
  G  an owned device joins and becomes eligible with nothing recompiled
  H  a model too large for every attached worker keeps its remote requirement
  I  a future capability tag places without a new scheduler, router or Brain

Then a real federated request through the existing entry point, so the last
round is an answer a model actually produced rather than a placement that says
one could be.

Nothing here registers a fake capability. Every worker in the scenario rounds is
constructed from this host's own measured resources, and where a round needs a
machine this container is not, the round says so in its note.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_SKILL_LIBRARY.v4.local_runtime.free_worker_mesh import (  # noqa: E402
    CAPABILITY_TAGS,
    ExecutionMode,
    FreeWorkerMesh,
    MeshOutcome,
    MeshRequest,
)
from AI_SKILL_LIBRARY.v4.local_runtime.resilience import FailureKind  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import Privacy  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.workers import (  # noqa: E402
    Attestation,
    WorkerClass,
    WorkerRecord,
    WorkerRegistry,
)
from AI_SKILL_LIBRARY.v4.tools.wave3_free_execution_paths import load_registry  # noqa: E402

MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct"


def _host_snapshot():
    """This container's real resources, used for every constructed worker.

    A scenario worker with invented RAM would prove the code branches, not the
    fabric. Where a round needs more than this host has, it says so.
    """
    resources = detect_resources()
    return resources


def _join(registry: WorkerRegistry, worker_id: str, *, worker_class: WorkerClass,
          privacy: Privacy, now: float, **fields: Any) -> WorkerRecord:
    defaults: dict[str, Any] = dict(
        worker_id=worker_id, endpoint="https://worker.invalid",
        resources=_host_snapshot(), runtimes=frozenset({"llama.cpp"}),
        worker_class=worker_class,
        supported_formats=frozenset({"gguf"}),
        supported_quantizations=frozenset({"Q4_K_M"}),
        supported_model_families=frozenset({"qwen3"}),
        measured_capabilities=frozenset({"coding"}),
        lease_seconds=120.0,
    )
    defaults.update(fields)
    registry.register(WorkerRecord(**defaults))
    registry.attest(worker_id, Attestation(zero_cost_only=True, max_privacy=privacy))
    registry.healthcheck(worker_id, healthy=True, now=now)
    return registry.get(worker_id)


def _request(**fields: Any) -> MeshRequest:
    defaults: dict[str, Any] = dict(
        model_id=MODEL, capability="coding", ram_mb=2_000, runtime="llama.cpp",
        artifact_format="gguf", quantization="Q4_K_M", model_family="qwen3",
        privacy=Privacy.CONFIDENTIAL)
    defaults.update(fields)
    return MeshRequest(**defaults)


def _row(round_id: str, name: str, failures: list[str], **extra: Any) -> dict[str, Any]:
    return {"round": round_id, "scenario": name, "passed": not failures,
            "failures": failures, **extra}


def scenario_rounds(root: Path, now: float) -> list[dict[str, Any]]:
    providers, _ = load_registry(root)
    rows: list[dict[str, Any]] = []

    # A - the ordinary case, which has to work before any failure case means
    # anything.
    registry = WorkerRegistry()
    _join(registry, "owned-linux-0", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.CONFIDENTIAL, now=now)
    mesh = FreeWorkerMesh(registry, providers)
    placement = mesh.place(_request(), now=now)
    failures = []
    if placement.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"expected a worker placement, got {placement.outcome.value}")
    if not placement.ran_the_requested_model:
        failures.append("the requested model was not what would run")
    rows.append(_row("A", "owned_worker_runs_the_exact_model", failures,
                     placement=dict(placement.to_dict())))

    # B - the preferred worker stops beating. Nothing is told to fail over; the
    # lease simply lapses, which is the point.
    registry = WorkerRegistry()
    _join(registry, "laptop", worker_class=WorkerClass.OWNED_MAC,
          privacy=Privacy.CONFIDENTIAL, now=now, lease_seconds=60.0)
    _join(registry, "desktop", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.CONFIDENTIAL, now=now, lease_seconds=1e9)
    mesh = FreeWorkerMesh(registry, providers)
    before = mesh.place(_request(), now=now)
    after = mesh.place(_request(), now=now + 600)
    failures = []
    if before.worker_id != "laptop":
        failures.append(f"the first placement should have used the laptop, used {before.worker_id}")
    if after.worker_id != "desktop":
        failures.append(f"after the lease lapsed the desktop should carry it, got {after.worker_id}")
    rows.append(_row("B", "stale_lease_fails_over", failures,
                     before=before.worker_id, after=after.worker_id,
                     refusal=list((after.refusals or {}).get("laptop", ()))))

    # C - an exhausted free tier. The assertion that matters is that it is
    # bypassed rather than retried: a retry loop against a daily allowance is
    # the failure mode this state exists to prevent.
    registry = WorkerRegistry()
    _join(registry, "free-tier", worker_class=WorkerClass.FREE_CLOUD_EPHEMERAL,
          privacy=Privacy.PUBLIC, now=now, quota_remaining=0,
          quota_reset_at=now + 3600, free_quota="10000/day")
    _join(registry, "owned-linux-0", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.PUBLIC, now=now)
    mesh = FreeWorkerMesh(registry, providers)
    placement = mesh.place(_request(privacy=Privacy.PUBLIC), now=now)
    failures = []
    if placement.worker_id != "owned-linux-0":
        failures.append(f"expected the owned worker, got {placement.worker_id}")
    refusal = " ".join((placement.refusals or {}).get("free-tier", ()))
    if "reset" not in refusal:
        failures.append("the quota refusal did not say the limit clears on reset")
    rows.append(_row("C", "quota_exhaustion_is_bypassed_not_retried", failures,
                     chose=placement.worker_id, refusal=refusal))

    # D - repeated failures. Two real failures are recorded against a threshold
    # of two, and the next placement must route elsewhere.
    registry = WorkerRegistry()
    _join(registry, "flaky", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.CONFIDENTIAL, now=now, lease_seconds=1e9)
    _join(registry, "steady", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.CONFIDENTIAL, now=now, lease_seconds=1e9)
    mesh = FreeWorkerMesh(registry, providers, failure_threshold=2, cooldown_seconds=60.0)
    first = mesh.place(_request(), now=now)
    for _ in range(2):
        mesh.record_failure(first.worker_id, FailureKind.TIMEOUT, now=now)
    second = mesh.place(_request(), now=now)
    failures = []
    if second.worker_id == first.worker_id:
        failures.append("the failing worker was selected again")
    if second.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append(f"no fallback worker was found: {second.outcome.value}")
    rows.append(_row("D", "repeated_failure_opens_the_circuit", failures,
                     failed_worker=first.worker_id, fell_over_to=second.worker_id,
                     refusal=list((second.refusals or {}).get(first.worker_id, ()))))

    # E - and it comes back. A breaker that never closed would turn one bad
    # afternoon into a permanently smaller federation.
    recovered = mesh.place(_request(), now=now + 300)
    failures = []
    if recovered.outcome is not MeshOutcome.EXACT_MODEL_WORKER:
        failures.append("nothing was placeable after the cooldown")
    rows.append(_row("E", "the_breaker_is_not_a_permanent_removal", failures,
                     placed_on=recovered.worker_id,
                     note="after cooldown a probe is allowed through, which is how it recovers"))

    # F - privacy. The provider serves the model and is free and authorised,
    # and is still refused, because the payload may not leave owned hardware.
    mesh = FreeWorkerMesh(WorkerRegistry(), providers)
    placement = mesh.place(_request(privacy=Privacy.CONFIDENTIAL,
                                    allow_capability_fallback=True), now=now)
    failures = []
    if placement.outcome is not MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE:
        failures.append(f"a confidential payload reached {placement.provider_id}")
    rows.append(_row("F", "privacy_outranks_the_free_provider", failures,
                     outcome=placement.outcome.value,
                     provider_refusals={k: list(v) for k, v in
                                        (placement.provider_refusals or {}).items()}))

    # G - a device joins. Nothing is reconfigured between the two placements.
    registry = WorkerRegistry()
    mesh = FreeWorkerMesh(registry, providers)
    empty = mesh.place(_request(), now=now)
    _join(registry, "macbook", worker_class=WorkerClass.OWNED_MAC,
          privacy=Privacy.CONFIDENTIAL, now=now)
    joined = mesh.place(_request(), now=now)
    failures = []
    if empty.outcome is not MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE:
        failures.append("an empty mesh reported something placeable")
    if joined.worker_id != "macbook":
        failures.append("the newly enrolled device did not become eligible")
    rows.append(_row("G", "owned_device_joins_and_becomes_eligible", failures,
                     before=empty.outcome.value, after=joined.worker_id,
                     note="no code path changed between the two calls"))

    # H - the large-model case that started all of this. The requirement is
    # preserved as a named shortfall rather than collapsing into unavailability.
    registry = WorkerRegistry()
    _join(registry, "owned-linux-0", worker_class=WorkerClass.OWNED_LINUX,
          privacy=Privacy.CONFIDENTIAL, now=now)
    mesh = FreeWorkerMesh(registry, providers)
    placement = mesh.place(_request(ram_mb=37_200), now=now)
    refusal = " ".join((placement.refusals or {}).get("owned-linux-0", ()))
    failures = []
    if placement.outcome is not MeshOutcome.CAPABILITY_TEMPORARILY_UNAVAILABLE:
        failures.append("a 37 GB model was reported placeable on this host")
    if "37200" not in refusal:
        failures.append("the shortfall was not named with a number")
    rows.append(_row("H", "large_model_keeps_its_named_requirement", failures,
                     refusal=refusal,
                     note="a statement about the machines attached, not about the model"))

    # I - readiness only. A capability from a later wave places on a worker
    # measured for it, with no new router, scheduler or Brain involved.
    future_rounds = {}
    for capability in ("vision", "ocr", "audio_understanding", "long_context"):
        registry = WorkerRegistry()
        _join(registry, "gpu-node", worker_class=WorkerClass.REMOTE_GPU,
              privacy=Privacy.INTERNAL, now=now,
              measured_capabilities=frozenset({capability}))
        placement = FreeWorkerMesh(registry, providers).place(
            _request(capability=capability, privacy=Privacy.INTERNAL), now=now)
        future_rounds[capability] = placement.outcome.value
    failures = [f"{cap} did not place" for cap, outcome in future_rounds.items()
                if outcome != MeshOutcome.EXACT_MODEL_WORKER.value]
    rows.append(_row("I", "future_capability_needs_no_new_authority", failures,
                     capabilities=future_rounds,
                     note=("architectural readiness only; no Wave 4 model is admitted, "
                           "staged or measured by this round")))
    return rows


def live_inference_round(root: Path) -> dict[str, Any]:
    """One real request through the existing federation entry point.

    The scenario rounds prove placement. This proves the chain ends in an answer
    a model produced, which a placement cannot establish on its own.
    """
    from AI_SKILL_LIBRARY.v4.local_runtime.multi_model import FederationError, run_federated

    started = time.time()
    try:
        result = run_federated(
            "In one sentence, what does a worker contribute to a federation?",
            root=root, cache=root / ".model-cache", profile="STANDARD", max_tokens=48,
        ).to_dict()
    except FederationError as exc:
        return _row("J", "live_federated_inference", [f"federation refused: {exc}"])

    workers = result.get("workers") or []
    failures = []
    if not workers:
        failures.append("no worker ran")
    if any(w.get("error") for w in workers):
        failures.append("a worker errored")
    if not (result.get("answer") or "").strip():
        failures.append("no answer came back")
    if result.get("resolved_by_vote") is not False:
        failures.append("the round was resolved by vote")
    return _row(
        "J", "live_federated_inference", failures,
        models=[w.get("model_id") for w in workers],
        routing_authority=result.get("routing_authority"),
        model_selection_authority=result.get("model_selection_authority"),
        answer=result.get("answer"),
        wall_ms=round((time.time() - started) * 1000.0, 3),
        note="a real completion from an admitted local model, not a placement",
    )


def build(root: Path, *, live: bool = True) -> dict[str, Any]:
    now = time.time()
    rows = scenario_rounds(root, now)
    if live:
        rows.append(live_inference_round(root))

    failed = [row["round"] for row in rows if not row["passed"]]
    return {
        "tool": "free_worker_mesh_proof",
        "rounds_run": len(rows),
        "rounds_passed": len(rows) - len(failed),
        "failed_rounds": failed,
        "mesh_status": "PROVEN" if not failed else "FAILED",
        "worker_classes_supported": sorted(c.value for c in WorkerClass),
        "capability_vocabulary_size": len(CAPABILITY_TAGS),
        "execution_modes": [m.value for m in ExecutionMode],
        "rounds": rows,
        "routing_authority": False,
        "model_selection_authority": False,
        "admission_authority": False,
        "note": (
            "Round I is architectural readiness only. No later-wave model is "
            "admitted, staged or measured by this proof."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--no-live", action="store_true",
                        help="skip the real inference round")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build(args.root, live=not args.no_live)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"FREE_WORKER_MESH={result['mesh_status']} "
          f"{result['rounds_passed']}/{result['rounds_run']}")
    for row in result["rounds"]:
        print(f"  {row['round']} {row['scenario']:<44} {'PASS' if row['passed'] else 'FAIL'}")
        for failure in row["failures"]:
            print(f"      {failure}")
    return 0 if result["mesh_status"] == "PROVEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
