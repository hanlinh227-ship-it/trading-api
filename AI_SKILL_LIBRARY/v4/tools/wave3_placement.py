"""Register the real workers, then say where each Wave 3 model can run.

    python AI_SKILL_LIBRARY/v4/tools/wave3_placement.py --evidence /tmp/place.json

Two things happen here and they are deliberately separate.

**This host is registered as a worker, from its own measurements.** Not a
description of it - `detect_resources()` reads the RAM, disk and GPUs that are
actually there, `detect_llama_cpp_python()` reads the backend that is actually
installed, and the worker attests to the limits it will honour. It registers as
`EPHEMERAL_LOCAL` because that is what it is: a container whose model cache dies
with it.

**Every Wave 3 model is then resolved against the registry.** The answer is a
placement state, not a yes/no, because "admitted" and "runnable here" are
different facts and the fix for each is different work.

The reframe this file exists for: the ~16 GB of RAM and the CRITICAL disk
watermark belong to *this container*. They are not operator hardware, not a
GitHub limit, and not a property of any model. A model that does not fit here is
`REMOTE_WORKER_REQUIRED` with the exact shortfall named, and the earlier
measurements are preserved untouched - what changes is the scope of the
conclusion drawn from them, which is the part that was wrong.

A worker registered here gains nothing by being registered. The registry refuses
to construct a worker with routing, reasoning, memory or model-selection
authority at all; those are class attributes, and passing one is a TypeError.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml  # noqa: E402

from AI_SKILL_LIBRARY.v4.local_runtime.backends.llama_cpp_python import (  # noqa: E402
    detect_llama_cpp_python,
)
from AI_SKILL_LIBRARY.v4.local_runtime.placement import (  # noqa: E402
    DISK_HEADROOM_MB,
    PlacementState,
    resolve,
)
from AI_SKILL_LIBRARY.v4.local_runtime.providers import ProviderRegistry  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.resources import detect_resources  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import Privacy  # noqa: E402
from AI_SKILL_LIBRARY.v4.local_runtime.workers import (  # noqa: E402
    Attestation,
    WorkerClass,
    WorkerRecord,
    WorkerRegistry,
    WorkerRequirement,
)

REGISTRY_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
WAVE3_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/wave3_knowledge_candidates.yaml"
EVIDENCE = "CHECKPOINTS/evidence"
CACHE_REL = ".model-cache/models"

#: This runtime's own backend reads GGUF and nothing else. Stated as a set so a
#: second backend is a registration change rather than a code change.
LOCAL_FORMATS = frozenset({"gguf"})

#: Quantizations this fleet has actually loaded, not the full llama.cpp list.
#: A quantization nobody here has executed is not a support claim.
LOCAL_QUANTIZATIONS = frozenset({"Q4", "Q4_K_M", "Q5_K_M", "Q8_0"})


def _load(root: Path, name: str) -> Any:
    try:
        return json.loads((root / EVIDENCE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def register_this_host(root: Path, registry: WorkerRegistry) -> WorkerRecord:
    """Register the container we are running in, from measurement."""
    resources = detect_resources()
    backend = detect_llama_cpp_python()
    snapshot = resources if not hasattr(resources, "to_dict") else resources

    families = sorted({
        str(model.get("family"))
        for model in (yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}).get("models", [])
        if model.get("family")
    })

    worker = WorkerRecord(
        worker_id="ephemeral-local-0",
        endpoint="http://127.0.0.1",
        resources=snapshot,
        runtimes=frozenset({"llama.cpp"}),
        worker_class=WorkerClass.EPHEMERAL_LOCAL,
        supported_formats=LOCAL_FORMATS,
        supported_quantizations=LOCAL_QUANTIZATIONS,
        supported_model_families=frozenset(families),
        max_context=131072,
        cost_class="owned_hardware_zero_marginal",
        network_reachable=True,
        last_verified_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    registry.register(worker)
    registry.attest(
        worker.worker_id,
        Attestation(
            # The container never leaves the host for inference and holds no
            # credential, so it may take confidential work. It runs on hardware
            # already paid for, so it is zero-cost.
            zero_cost_only=True,
            max_privacy=Privacy.CONFIDENTIAL,
            shell_execution=False,
            financial_execution=False,
            credential_storage=False,
        ),
    )
    registry.healthcheck(worker.worker_id, healthy=bool(backend and backend.backend_version), now=time.time())
    return registry.get(worker.worker_id)


def cached_models(root: Path) -> dict[str, list[str]]:
    """Which workers hold which artifact, by digest, read from the cache."""
    out: dict[str, list[str]] = {}
    cache = root / CACHE_REL
    if not cache.is_dir():
        return out
    for manifest in cache.rglob("*.manifest.json"):
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        # The intake manifest names it artifact_sha256. Reading the wrong key
        # made every cached model look un-cached, which turned a resident
        # artifact into a JIT acquisition of bytes already on disk.
        digest = str(
            doc.get("artifact_sha256") or doc.get("sha256") or doc.get("expected_sha256") or ""
        ).lower()
        if digest:
            out.setdefault(digest, []).append("ephemeral-local-0")
    return out


def load_free_paths(root: Path) -> tuple[ProviderRegistry, dict[str, Any]]:
    """The recorded zero-cost paths, or nothing if the file is not there yet."""
    from AI_SKILL_LIBRARY.v4.tools.wave3_free_execution_paths import load_registry

    try:
        return load_registry(root)
    except (OSError, ValueError):
        return ProviderRegistry(), {}


def build(root: Path) -> dict[str, Any]:
    registry = WorkerRegistry()
    host = register_this_host(root, registry)

    models = (yaml.safe_load((root / REGISTRY_REL).read_text(encoding="utf-8")) or {}).get("models", [])
    by_id = {str(m.get("model_id")): m for m in models}
    wave3 = yaml.safe_load((root / WAVE3_REL).read_text(encoding="utf-8")) or {}

    # Measured peaks beat estimates. Read from the residency profile, which is
    # the only place a real peak RSS for each model is recorded.
    profile = _load(root, "RESIDENCY_LATENCY_PROFILE.json") or {}
    peaks = {
        str(row.get("model_id")): row.get("peak_ram_mb")
        for row in profile.get("models", [])
    }

    incompatible = set()
    incompat_doc = _load(root, "RUNTIME_INCOMPATIBILITY_EVIDENCE.json") or {}
    for row in incompat_doc.get("records", []):
        digest = str(row.get("artifact_sha256") or "").lower()
        for model in models:
            if str((model.get("artifact_identity") or {}).get("sha256") or "").lower() == digest:
                incompatible.add(str(model.get("model_id")))

    # Hosted paths are consulted only where every worker has been ruled out, so
    # a model that runs on our own hardware keeps that answer.
    providers, _ = load_free_paths(root)

    cache = cached_models(root)
    placements = []
    for model in models:
        digest = str((model.get("artifact_identity") or {}).get("sha256") or "").lower()
        placement = resolve(
            model,
            registry,
            cached_on=cache.get(digest, []),
            measured_peak_ram_mb=peaks.get(str(model.get("model_id"))),
            runtime_incompatible=str(model.get("model_id")) in incompatible,
            providers=providers,
        )
        placements.append(placement.to_dict())

    # Wave 3 candidates with no registry row yet still need a placement answer,
    # because "we could not run it even if it were admitted" is worth knowing
    # before the admission work rather than after.
    unadmitted = []
    for candidate in wave3.get("candidates", []):
        upstream = str(candidate.get("upstream"))
        if upstream in by_id or any(upstream in k for k in by_id):
            continue
        req = candidate.get("worker_requirement") or {}
        ram_mb = int(req.get("runtime_ram_mb") or 0)
        disk_mb = int(req.get("artifact_mb") or 0) + DISK_HEADROOM_MB
        requirement = WorkerRequirement(
            runtime="llama.cpp",
            ram_mb=ram_mb,
            disk_mb=disk_mb,
            privacy=Privacy.CONFIDENTIAL,
            free_only=True,
        )
        fits = registry.eligible(requirement)
        blockers = {} if fits else registry.refusals(requirement)
        hosted = providers.resolve(upstream, free_only=True)
        # Two different unavailabilities. A candidate no worker can hold needs a
        # machine; one that would fit but has no verified artifact needs
        # admission work. Collapsing them would send an operator to buy RAM for
        # a provenance problem.
        # The manifest keys this as `state`; `status` is read too so a rename
        # upstream degrades into the licence gate holding rather than silently
        # lapsing into a capacity answer.
        status = str(candidate.get("state") or candidate.get("status") or "")
        if status == "ARTIFACT_PROVENANCE_INCOMPLETE":
            # A worker meets its memory requirement, so reporting capacity here
            # would say the remaining work is a machine. It is not: every
            # artifact on offer fails the provenance rule, and that is refused
            # rather than waived.
            state = "ARTIFACT_PROVENANCE_INCOMPLETE"
            note = ("a worker meets this candidate's memory requirement, so capacity is "
                    "not the blocker. No artifact exists whose conversion names both its "
                    "base revision and the tool that produced it, and a build that cannot "
                    "say what it was made from is refused whoever published it.")
        elif status == "HUMAN_LICENSE_GATE_REQUIRED":
            # Capacity is not this candidate's blocker and reporting one would
            # imply the remaining work is technical. It is not: a person has to
            # accept the publisher's terms, and nothing here may do that for
            # them.
            state = "HUMAN_LICENSE_GATE_REQUIRED"
            note = ("a worker's capacity is irrelevant here. The blocker is a licence "
                    "only the operator can accept; this candidate is deferred and is "
                    "not staged, downloaded or admitted.")
        elif fits:
            state = "ADMISSION_PENDING_WORKER_AVAILABLE"
            note = (f"a worker meets the {ram_mb} MB RAM requirement; the blocker is "
                    f"artifact provenance, not capacity")
        elif hosted.has_exact:
            # No machine of ours can hold it and none needs to: a zero-cost
            # provider serves this same model. Reporting it as needing a worker
            # would send an operator to buy RAM for a solved problem.
            provider_id, offering = hosted.exact[0]
            state = "AVAILABLE_SERVERLESS"
            note = (f"{provider_id} serves this exact model as {offering.provider_model_id} "
                    f"on a zero-cost path, so the {ram_mb} MB requirement does not bind")
        elif hosted.capability:
            provider_id, offering = hosted.capability[0]
            state = "PROVIDER_CAPABILITY_FALLBACK"
            note = (f"this model still runs nowhere. {provider_id} serves "
                    f"{offering.provider_model_id}, which covers the capability under its "
                    f"own name and must not be measured as this one")
        elif hosted.pending:
            # A provider does serve it; what is missing is proof that its free
            # tier will. That is one probe, not a machine, and saying "needs a
            # worker" here would send an operator to provision hardware for a
            # question a single request answers.
            state = "PROVIDER_PATH_PENDING_VERIFICATION"
            names = ", ".join(sorted(hosted.pending))
            note = (f"no attached worker meets the {ram_mb} MB requirement, but {names} "
                    f"serves it. What is unproven is free-tier eligibility, which the "
                    f"Workers AI probe settles; until it returns a completion this stays "
                    f"unverified rather than available.")
        else:
            state = "REMOTE_WORKER_REQUIRED"
            note = (f"needs a worker with at least {ram_mb} MB RAM and {disk_mb} MB free "
                    f"disk. No attached worker meets that, and no zero-cost provider "
                    f"serves it. This is a statement about the machines currently online "
                    f"and the paths currently recorded, not about the model.")
        unadmitted.append({
            "candidate_id": candidate.get("id"),
            "upstream": upstream,
            "placement_state": state,
            "worker_class_required": req.get("worker_class_min"),
            "estimated_runtime_ram_mb": ram_mb,
            "estimated_disk_mb": disk_mb,
            "requirement_basis": req.get("basis"),
            "requirement_is_an_estimate": bool(req.get("estimated", True)),
            "blockers": {k: list(v) for k, v in sorted(blockers.items())},
            "zero_cost_provider_paths": dict(hosted.to_dict()),
            "note": note,
        })

    by_state: dict[str, list[str]] = {}
    for row in placements:
        by_state.setdefault(row["state"], []).append(row["model_id"])

    return {
        "tool": "wave3_placement",
        "host_worker": host.to_dict(now=time.time()),
        "host_limits_are_scoped_to_this_container": True,
        "workers": registry.to_dict(now=time.time()),
        "worker_count": len(registry.all()),
        "placements": placements,
        "by_state": {state: sorted(ids) for state, ids in sorted(by_state.items())},
        "unadmitted_candidates": unadmitted,
        "executable_now": sorted(
            row["model_id"] for row in placements if row["executable"]
        ),
        "routing_authority": False,
        "model_selection_authority": False,
        "admission_authority": False,
        "note": (
            "Capacity report. A REMOTE_WORKER_REQUIRED state describes the machines "
            "currently attached, never the model: the same model on a larger worker "
            "is AVAILABLE without any change to its governance record."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)

    result = build(Path(args.root).resolve())
    if args.evidence:
        Path(args.evidence).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    host = result["host_worker"]
    print(f"WAVE3_PLACEMENT workers={result['worker_count']} "
          f"executable_now={len(result['executable_now'])}/{len(result['placements'])}")
    print(f"  host {host['worker_id']} {host['worker_class']} "
          f"ram={host['available_ram_mb']}MB disk={host['available_disk_mb']}MB "
          f"state={host['state']}")
    for row in result["placements"]:
        worker = row["worker_id"] or "-"
        acq = " (JIT acquire)" if row["requires_acquisition"] and row["executable"] else ""
        print(f"  {row['state']:<38} {row['model_id']:<45} {worker}{acq}")
        if not row["executable"]:
            for name, why in row["blockers"].items():
                print(f"      {name}: {'; '.join(why)}")
    for row in result["unadmitted_candidates"]:
        print(f"  {row['placement_state']:<38} {row['upstream']:<45} "
              f"~{row['estimated_runtime_ram_mb']}MB RAM")
        for name, why in (row.get("blockers") or {}).items():
            print(f"      {name}: {'; '.join(why)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
