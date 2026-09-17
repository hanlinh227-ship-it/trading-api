"""B3/B4: drive the canonical golden-trace gate with the real runtime.

`v4/control_plane/e2e.py` already owns what B3 and B4 mean. It defines the
exact trace, demands the runtime evidence fields, and refuses anything marked
synthetic or fixture-only. So this module adds no gate of its own - it supplies
the callables that gate injects, backed by the same canonical components the B2
route uses. Writing a second E2E runner here would mean two definitions of
"passed", and the one that fails would simply be the one nobody ran.

Every callable is an adapter over something real:

    router      -> route_request, reading stable/router.yaml
    selector    -> the Model Mesh's own filters and scoring
    runtime     -> llama.cpp, loaded with egress denied
    verifier    -> checks the execution against the selection; can fail
    synthesis   -> the model's own tokens, not a restatement of them

The two fields B4 turns on are the ones easiest to assert and hardest to earn,
so neither is a constant here:

* `offline` is computed from the environment actually in force at load time -
  no proxy variable present and a local in-process runtime - rather than
  written as True because the code path is believed to be local.
* `lifecycle` wake/warm/sleep are three observed facts: a load that happened, a
  second invocation that reused the resident handle instead of paying for the
  load again, and an unload that actually freed it. A model that never woke
  cannot report `wake: True` from here.
"""

from __future__ import annotations

import datetime
import os
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .backends.llama_cpp_python import LlamaCppPythonBackend, detect_llama_cpp_python
from .evidence import PeakSampler
from .canonical_route import LOCAL_PROVIDER_ID, as_mesh_candidate, mesh_select, route_request
from .identity import from_record
from .projection import load_registry, project_record
from .runtime import TaskContract
from .staging import resolve_cached

#: Proxy variables whose absence is part of the offline claim.
_EGRESS_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")

#: Runtimes that are not local execution, mirroring the gate's own rejection.
_REMOTE_RUNTIMES = {"hosted_api", "cloud_api"}


class GoldenE2EError(RuntimeError):
    """The real path could not be driven. Never a substitute for a failed gate."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def deny_egress() -> dict[str, str]:
    removed = {}
    for name in _EGRESS_VARS:
        value = os.environ.pop(name, None)
        if value is not None:
            removed[name] = "<removed>"
    os.environ["NO_PROXY"] = "*"
    return removed


def observed_offline(runtime_name: str) -> bool:
    """Offline as an observation, not a claim.

    True only when no proxy variable is present in the environment the load
    ran under and the runtime is a local one. An in-process GGUF load performs
    no network I/O of its own, so this is a second control rather than the only
    one - but it is checkable, which a hardcoded True is not.
    """
    if any(os.environ.get(name) for name in _EGRESS_VARS):
        return False
    return runtime_name.lower() not in _REMOTE_RUNTIMES


# -- the injected callables ------------------------------------------------


def make_router(root: Path):
    def router(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
        routed = route_request(str(envelope.get("request") or ""), root=root)
        return {
            "routed_by": "task_router",
            "domain": routed["domain"],
            "primary_skill": routed["primary_skill"],
            "profile": str(envelope.get("profile") or "STANDARD"),
        }
    return router


def ingress(envelope: Mapping[str, Any], route: Mapping[str, Any]) -> Mapping[str, Any]:
    """Carry the request forward. Names no model, and cannot."""
    return {
        "request_id": str(envelope.get("request_id") or f"b3-{int(time.time())}"),
        "request": str(envelope.get("request") or ""),
        "model_named_at_ingress": False,
        "selection_request": {
            "domain": route["domain"],
            "primary_skill": route["primary_skill"],
            "data_class": str(envelope.get("data_class") or "PUBLIC"),
        },
    }


def gate_identity(identity: Any) -> dict[str, Any]:
    """The verified artifact, in the shape the canonical record declares it.

    Used by the runtime side only. The selector reads the record's declared
    `artifact_identity` block instead, so the gate's identity comparison is
    between what governance *claims* and what was *verified on disk* - two
    independent paths. Having the runtime echo the selection back would make
    that comparison compare a value with itself and always pass.
    """
    return {
        "model_id": identity.model_id,
        "family": identity.family,
        "variant": identity.variant,
        "immutable_revision": identity.immutable_revision,
        "sha256": identity.artifact_sha256,
        "size_bytes": identity.artifact_size_bytes,
        "format": identity.artifact_format,
        "quantization": identity.quantization,
    }


def make_selector(identities: Mapping[str, Mapping[str, Any]]):
    """`identities` maps candidate key -> the record's declared identity block."""

    def selector(request: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        winner, rejections = mesh_select(
            list(candidates),
            domain=str(request.get("domain")),
            primary_skill=str(request.get("primary_skill")),
            data_class=str(request.get("data_class") or "PUBLIC"),
        )
        if winner is None:
            raise GoldenE2EError(
                "Model Mesh selected no candidate: " + ("; ".join(rejections) or "no candidates offered")
            )
        key = f"{winner.get('provider_id')}:{winner.get('model_id')}"
        declared = identities.get(key)
        if declared is None:
            raise GoldenE2EError(f"selected {key} has no declared artifact identity")
        return {
            "primary_model": {
                "candidate_key": key,
                "artifact_identity": dict(declared),
            },
            "supporting_models": [],
            "verifier": str(request.get("primary_skill")),
            "fallback_chain": [],
            "evidence_refs": [],
            "resource_plan": {},
            "rejections": rejections,
        }
    return selector


def make_runtime(root: Path, cache: Path, records: Mapping[str, Mapping[str, Any]],
                 *, max_tokens: int = 24):
    """Load the real weights the mesh selected, and measure wake, warm, sleep.

    `records` maps candidate key -> registry record. It used to be a single
    record, which was indistinguishable from correct while exactly one model was
    admitted and became a mis-execution the moment four were: the mesh selected
    Qwen3-4B and the runtime loaded Qwen3-0.6B, ignoring the selection
    entirely. The golden gate caught it as an artifact_identity_mismatch,
    because the identity it compares reaches it by two independent paths.
    """

    def runtime(selection: Mapping[str, Any], prepared: Mapping[str, Any]) -> Mapping[str, Any]:
        key = str(selection["primary_model"].get("candidate_key") or "")
        record = records.get(key)
        if record is None:
            raise GoldenE2EError(f"the mesh selected {key}, which has no registry record here")
        identity, reasons = from_record(record)
        if identity is None:
            raise GoldenE2EError("; ".join(reasons))
        artifact = resolve_cached(cache, record, verify=True)
        if artifact is None:
            raise GoldenE2EError("no verified artifact cached for this identity")

        backend_identity = detect_llama_cpp_python()
        backend = LlamaCppPythonBackend(backend_identity)
        if not backend.healthy():
            raise GoldenE2EError("no real llama.cpp runtime available")

        deny_egress()
        started_at = _now()
        context_limit = min(int(record.get("context_window") or 2048), 4096)
        prompt = str(prepared.get("request") or "")

        def generate(task_id: str) -> Mapping[str, Any]:
            return backend.execute(
                TaskContract(task_id=task_id, model_id=identity.model_id,
                             payload={"prompt": prompt}, max_output_tokens=max_tokens,
                             timeout_seconds=600.0),
                backend.probe(),
            )

        load_started = time.monotonic()
        with PeakSampler() as sampler:
            backend.load(identity.model_id, artifact,
                         context_limit=context_limit, quantization=identity.quantization)
            load_ms = round((time.monotonic() - load_started) * 1000.0, 3)
            # wake: a load actually happened and the model is resident.
            woke = backend.is_loaded(identity.model_id)
            resident_before = backend.resident(identity.model_id)

            first = generate(f"{prepared['request_id']}-cold")
            warm_started = time.monotonic()
            second = generate(f"{prepared['request_id']}-warm")
            warm_ms = round((time.monotonic() - warm_started) * 1000.0, 3)
            # warm: the second invocation ran against the *same* resident
            # handle, so it paid no load.
            #
            # An earlier version asserted warm_ms < load_ms, which sounds like
            # evidence and is close to a tautology: an inference is shorter
            # than a multi-second model load whether or not anything was
            # reused. The measured numbers make that plain - cold inference
            # ~703ms against warm ~718ms, because the load was already paid
            # before the first generate, so warm inference is not faster than
            # cold inference at all. Object identity is the fact that actually
            # distinguishes a reused resident from a reloaded one.
            resident_after = backend.resident(identity.model_id)
            warm = (
                backend.is_loaded(identity.model_id)
                and resident_before is not None
                and resident_after is resident_before
            )

        # sleep: the unload actually freed the slot.
        released = backend.unload(identity.model_id)
        slept = released and not backend.is_loaded(identity.model_id)
        ended_at = _now()

        return {
            "real_inference": True,
            "synthetic": False,
            "fixture_only": False,
            # The identity of the bytes that were verified and loaded, derived
            # independently of what the selector was told.
            "artifact_identity": gate_identity(identity),
            "runtime": backend.name,
            "runtime_version": backend_identity.backend_version,
            "offline": observed_offline(backend.name),
            "started_at": started_at,
            "ended_at": ended_at,
            "load_latency_ms": load_ms,
            "inference_latency_ms": first.get("inference_latency_ms"),
            "warm_inference_latency_ms": warm_ms,
            "peak_ram_mb": sampler.peak_mb,
            "output": first["text"],
            "warm_output": second["text"],
            "raw_run_ref": f"{identity.fingerprint}:{prepared['request_id']}",
            "lifecycle": {"wake": woke, "warm": warm, "sleep": slept},
            "tokens_input": first.get("tokens_input"),
            "tokens_output": first.get("tokens_output"),
        }

    return runtime


def verifier(kind: Any, execution: Mapping[str, Any]) -> Mapping[str, Any]:
    """Check the run against itself. Able to fail, or it verifies nothing.

    Deliberately checks properties that a broken or faked run would get wrong,
    and nothing about whether the answer is *good* - judging answer quality is
    the grader's job and would make this gate unfalsifiable.
    """
    failures: list[str] = []
    if not str(execution.get("output") or "").strip():
        failures.append("empty_output")
    if execution.get("real_inference") is not True:
        failures.append("not_real_inference")
    for field in ("load_latency_ms", "inference_latency_ms"):
        value = execution.get(field)
        if not isinstance(value, (int, float)) or value <= 0:
            failures.append(f"implausible_{field}")
    if not str(execution.get("raw_run_ref") or "").strip():
        failures.append("no_raw_run_reference")
    identity = execution.get("artifact_identity")
    if not isinstance(identity, Mapping) or len(str(identity.get("sha256") or "")) != 64:
        failures.append("artifact_identity_not_digest_bound")
    return {"passed": not failures, "failures": failures,
            "evidence_refs": [str(execution.get("raw_run_ref") or "")], "verifier": str(kind)}


def synthesis(prepared: Mapping[str, Any], execution: Mapping[str, Any],
              verification: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "request_id": prepared["request_id"],
        "answer": execution["output"],
        "verified": verification.get("passed") is True,
        "evidence_refs": list(verification.get("evidence_refs") or []),
        "produced_by": execution.get("runtime"),
    }


# -- assembling the inputs the gate needs ----------------------------------


def admitted_candidates(root: Path, *, observed_at: str | None = None):
    """Governance-admitted local models, as Model Mesh candidates."""
    observed_at = observed_at or _now()
    registry = load_registry(root)
    out: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for record in registry.get("models") or []:
        if not isinstance(record, Mapping):
            continue
        projected = project_record(record, available_runtimes=["llama.cpp"])
        if not projected.placeable or projected.profile is None:
            continue
        out.append((as_mesh_candidate(projected.profile, record, observed_at=observed_at), record))
    return out


def records_by_key(pairs) -> dict[str, Mapping[str, Any]]:
    """Candidate key -> its registry record, so the runtime loads what was picked."""
    return {f"{candidate.get('provider_id')}:{candidate.get('model_id')}": record
            for candidate, record in pairs}


def declared_identities(pairs) -> dict[str, Mapping[str, Any]]:
    """Candidate key -> the identity block the canonical record declares."""
    index: dict[str, Mapping[str, Any]] = {}
    for candidate, record in pairs:
        key = f"{candidate.get('provider_id')}:{candidate.get('model_id')}"
        block = record.get("artifact_identity")
        if isinstance(block, Mapping):
            index[key] = dict(block)
    return index
