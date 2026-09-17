"""Run a federation plan across several admitted local models.

Every decision here is made somewhere else and this executes the result. That
division is the point, so it is worth being explicit about who owns what:

    task_router                 the domain and primary skill
    Model Mesh select_workers   which models, bounded and family-diverse
    control_plane plan_execution  how many may run, and whether a verifier runs
    this module                 running them and recording what came back

No new orchestrator, no new router, no new cap. `plan_execution` already encodes
FAST=1 / STANDARD=2 / DEEP=4 and already decides that FAST gets no verifier;
`select_workers` already refuses to fill two slots with two variants of one
family. Re-deciding any of that here would be the duplicate authority the
architecture forbids, so the executor reads the plan and does what it says.

**The checker does not vote.** When a plan runs two models, the second is there
to check, and its disagreement is recorded as disagreement - not resolved by
counting. Two models agreeing is not evidence that either is right, and a
majority of three would be worse, because it would look like proof. So the
result carries both answers, an explicit `agreement` flag, and the primary's
answer as the answer. Anything that needs adjudicating goes to a verifier or to
a human, which is what unresolved means.
"""

from __future__ import annotations

import datetime
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from AI_SKILL_LIBRARY.v4.control_plane.federation import plan_execution  # noqa: E402
from AI_SKILL_LIBRARY.v4.tools import model_mesh as mesh  # noqa: E402

from .backends.llama_cpp_python import LlamaCppPythonBackend, detect_llama_cpp_python  # noqa: E402
from .canonical_route import LOCAL_PROVIDER_ID, as_mesh_candidate, mesh_select, route_request  # noqa: E402
from .golden_e2e import deny_egress  # noqa: E402
from .identity import from_record  # noqa: E402
from .projection import load_registry, project_record  # noqa: E402
from .runtime import TaskContract  # noqa: E402
from .staging import resolve_cached  # noqa: E402

#: Greedy, and the state reset between models so one model's context cannot
#: leak into another's answer - which would make an "independent" check anything
#: but independent.
#: Greedy and state-reset, so two identical requests give identical answers.
#:
#: `chat` applies each model's own embedded template. Without it an
#: instruction-tuned model handed a bare prompt can emit end-of-turn
#: immediately and return nothing - Phi-3-mini does exactly that, and it was
#: silently failing as checker on prompts the maker answered fine. Using the
#: template the GGUF already carries fixes it for every such model without a
#: per-model table to keep in step.
#:
#: The benchmark suites deliberately do NOT set this. Their scores were measured
#: through the raw completion path and are bound to artifact digests; moving
#: them to a different prompt encoding would change the numbers under records
#: that were already sealed.
DECODING: Mapping[str, Any] = {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "seed": 0,
                               "reset_state": True, "chat": True}


class FederationError(RuntimeError):
    """The plan could not be executed. Never a substitute for a failed check."""


@dataclass(frozen=True)
class WorkerResult:
    model_id: str
    role: str
    output: str | None
    latency_ms: float | None
    error: str | None = None

    def to_dict(self) -> Mapping[str, Any]:
        return {"model_id": self.model_id, "role": self.role, "output": self.output,
                "latency_ms": self.latency_ms, "error": self.error}


@dataclass(frozen=True)
class FederationResult:
    request: str
    profile: str
    domain: str
    primary_skill: str
    mode: str
    answer: str | None
    workers: tuple[WorkerResult, ...]
    outputs_identical: bool | None
    plan: Mapping[str, Any] = field(default_factory=dict)
    rejections: tuple[str, ...] = ()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "request": self.request,
            "profile": self.profile,
            "domain": self.domain,
            "primary_skill": self.primary_skill,
            "collaboration_mode": self.mode,
            "answer": self.answer,
            "workers": [w.to_dict() for w in self.workers],
            # Literally whether the two strings match. None when only one
            # model ran, because there was nothing to compare.
            "outputs_identical": self.outputs_identical,
            # Substantive agreement is a judgement and belongs to the verifier.
            # Recorded as unresolved rather than inferred from string equality.
            "substantive_agreement": "unresolved_here",
            "resolved_by_vote": False,
            "max_concurrent_models": self.plan.get("max_concurrent_models"),
            "verifier": self.plan.get("verifier"),
            "specialist_groups": list(self.plan.get("specialist_groups") or []),
            "routing_authority": "task_router",
            "model_selection_authority": "model_mesh",
            "execution_plan_authority": "control_plane.plan_execution",
            "rejections": list(self.rejections),
        }


def admitted(root: Path, observed_at: str):
    """Governance-admitted local models as (candidate, record) pairs."""
    pairs = []
    for record in load_registry(root).get("models") or []:
        projected = project_record(record, available_runtimes=["llama.cpp"])
        if not projected.placeable or projected.profile is None:
            continue
        pairs.append((as_mesh_candidate(projected.profile, record, observed_at=observed_at), record))
    return pairs


def _worker_task(domain: str, primary_skill: str, profile: str,
                 candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The task shape `select_workers` expects.

    Permission, quota and reputation are supplied per candidate because the mesh
    requires them explicitly rather than assuming a default - a candidate with no
    entry is simply not permitted, which is the right way round.
    """
    keys = [f"{c.get('provider_id')}:{c.get('model_id')}" for c in candidates]
    return {
        "profile": profile,
        "domain": domain,
        "primary_skill": primary_skill,
        "data_class": "PUBLIC",
        "role": "specialist",
        "permission_allowed": {key: True for key in keys},
        # A locally-resident model has no provider quota to exhaust; the
        # constraint is RAM, and that belongs to the scheduler.
        "quota_headroom": {key: 1.0 for key in keys},
        # The mesh's neutral default. This lane has no operating history yet,
        # and inventing one would rig the ranking it feeds.
        "reputation": {key: 0.5 for key in keys},
    }


def run_federated(request: str, *, root: Path, cache: Path, profile: str = "STANDARD",
                  max_tokens: int = 32) -> FederationResult:
    """Route, plan, run. Raises only if the plan itself cannot be built."""
    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    routed = route_request(request, root=root)
    domain, primary_skill = routed["domain"], routed["primary_skill"]

    pairs = admitted(root, observed_at)
    if not pairs:
        raise FederationError("no governance-admitted local model")
    candidates = [candidate for candidate, _ in pairs]
    records = {f"{c.get('provider_id')}:{c.get('model_id')}": record for c, record in pairs}

    winner, rejections = mesh_select(candidates, domain=domain, primary_skill=primary_skill)
    if winner is None:
        raise FederationError("; ".join(rejections) or "the mesh selected no candidate")

    primary_key = f"{winner.get('provider_id')}:{winner.get('model_id')}"
    supporting = [
        worker for worker in mesh.select_workers(
            _worker_task(domain, primary_skill, profile, candidates),
            list(candidates), max_workers=4,
        )
        if f"{worker.get('provider_id')}:{worker.get('model_id')}" != primary_key
    ]

    plan = plan_execution(
        profile,
        {
            "primary_model": {"candidate_key": primary_key, "model_id": winner.get("model_id")},
            "supporting_models": [
                {"candidate_key": f"{w.get('provider_id')}:{w.get('model_id')}",
                 "model_id": w.get("model_id")}
                for w in supporting
            ],
            "verifier": primary_skill,
        },
        [primary_skill.upper()],
    )

    planned = list(plan.get("models") or [])
    mode = "SOLO" if len(planned) < 2 else "MAKER_CHECKER"

    deny_egress()
    backend_identity = detect_llama_cpp_python()
    if backend_identity is None:
        raise FederationError("no real llama.cpp runtime available")
    backend = LlamaCppPythonBackend(backend_identity)

    results: list[WorkerResult] = []
    for index, entry in enumerate(planned):
        key = str(entry.get("candidate_key"))
        record = records.get(key)
        role = "maker" if index == 0 else "checker"
        if record is None:
            results.append(WorkerResult(key, role, None, None, "no registry record for planned model"))
            continue
        identity, reasons = from_record(record)
        artifact = resolve_cached(cache, record, verify=True) if identity else None
        if identity is None or artifact is None:
            results.append(WorkerResult(key, role, None, None,
                                        "; ".join(reasons) or "no verified artifact cached"))
            continue
        try:
            backend.load(identity.model_id, artifact,
                         context_limit=min(int(record.get("context_window") or 2048), 4096),
                         quantization=identity.quantization)
            started = time.monotonic()
            out = backend.execute(
                TaskContract(task_id=f"fed-{index}", model_id=identity.model_id,
                             payload={"prompt": request, **DECODING},
                             max_output_tokens=max_tokens, timeout_seconds=600.0),
                backend.probe(),
            )
            latency = round((time.monotonic() - started) * 1000.0, 3)
            results.append(WorkerResult(identity.model_id, role, out["text"], latency))
        except Exception as exc:  # noqa: BLE001 - a worker failure is data
            results.append(WorkerResult(identity.model_id, role, None, None,
                                        f"{type(exc).__name__}: {exc}"))
        finally:
            # Unload between workers. Two multi-gigabyte models resident at once
            # is exactly what the residency budget exists to prevent.
            backend.unload(identity.model_id)

    answers = [r.output.strip() for r in results if r.output]
    # What is actually measured is whether two strings are identical, and that
    # is all this reports. Two models answering "The capital city of Japan is
    # Tokyo. However," and "\n\nThe capital city of Japan is Tokyo." agree
    # completely and differ as text, so calling string inequality
    # "disagreement" would manufacture a conflict signal - and a confidence
    # escalation triggered by it would burn a DEEP round on nothing.
    #
    # Whether two answers agree in substance is a judgement, and judgement is
    # the verifier's job. So the field says what it is, and substantive
    # agreement stays unresolved here rather than being guessed.
    outputs_identical = None
    if len(answers) >= 2:
        outputs_identical = answers[0] == answers[1]

    primary_answer = next((r.output for r in results if r.role == "maker" and r.output), None)
    return FederationResult(
        request=request, profile=plan["profile"], domain=domain, primary_skill=primary_skill,
        mode=mode, answer=primary_answer, workers=tuple(results),
        outputs_identical=outputs_identical,
        plan=plan, rejections=tuple(rejections),
    )
