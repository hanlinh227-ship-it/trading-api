"""Open Model Universe record -> runtime ModelProfile.

Read-only, in one direction. This module reads the registry the research lane
owns and produces the profile this lane's scheduler consumes. It never writes
to the registry, never fills a field the registry left empty, and never turns
an absent value into a usable one.

The whole design is one sentence: **a registry row is a claim, and a claim is
not evidence.** So every row arrives INELIGIBLE and has to earn ADMITTED by
clearing every gate in `GATES`, each of which returns a sentence saying exactly
what was missing. A row that clears everything except artifact identity is
`RESTRICTED`: good enough to place if the weights are already on disk, not good
enough to start a download.

Three things this deliberately will not do:

* **Invent a number.** The registry carries `quality_class` as free text, not a
  score. Projection copies the class and leaves `quality` as `None`; the
  scheduler then uses a neutral prior and the placement plan reports the
  quality as unevidenced. Mapping classes to numbers needs a table the research
  lane owns.
* **Trust a runtime-bearing state.** A registry row saying `RUNNING` means
  somebody wrote `RUNNING` in a YAML file. Runtime state is observed here, not
  read from metadata, so those states project to their pre-runtime equivalent
  and the claim is recorded as unverified.
* **Coerce unknown to zero.** A null `minimum_ram_gb` stays `None` and the
  scheduler refuses the placement it cannot prove, rather than reading it as
  "needs no RAM".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .admission_policy import AdmissionPolicy, load_admission_policy
from .identity import artifact_block
from .lifecycle import ModelState
from .reconciliation import registry_state_is_runtime_bearing
from .resources import ResourceSnapshot
from .scheduler import AdmissionStatus, ModelProfile, Privacy, Tri

_GB_TO_MB = 1024

#: Registry runtime names -> this lane's adapter names.
RUNTIME_NAME_MAP: Mapping[str, str] = {
    "llama_cpp": "llama.cpp",
    "ollama": "ollama",
    "vllm": "vllm",
    "sglang": "sglang",
    "transformers": "transformers",
    "mlx": "mlx",
    "tgi": "tgi",
    "lmdeploy": "lmdeploy",
    "other": "other",
}

#: Revisions that look pinned but move. Kept in step with `acquisition.py`.
FLOATING_REVISIONS = {"main", "master", "latest", "head", "trunk", "dev", "stable"}

#: Cost classes that satisfy zero-paid-token-first. `unknown` is not among
#: them: the policy is "provably free", not "not known to cost anything".
ZERO_COST_CLASSES = frozenset(
    {
        "zero_paid_token_candidate",
        "owned_hardware_zero_marginal",
        "verified_recurring_free",
        "verified_free_quota_hard_stop",
    }
)

#: Licence classes that may not be placed at all.
BLOCKING_LICENSE_CLASSES = frozenset({"restricted", "unclear"})

#: Registry lifecycle states from which a model may be placed.
#:
#: Derived from `admission_policy.yaml`, not decided here: the policy requires
#: AVAILABLE and lists everything else - APPROVED included - among its blocked
#: states. A test asserts this stays equal to the policy's requirement, so the
#: constant cannot drift away from the file it mirrors. It exists as a constant
#: only to keep import time free of file IO.
PLACEABLE_STATES = frozenset({"AVAILABLE"})

#: Privacy classes meaning "local candidate, security admission still pending".
#: Distinct from an unrecognised class: this one is understood, and understood
#: to mean not-yet-cleared. Deliberately absent from PRIVACY_CLASS_MAP so it can
#: never resolve to a usable ceiling.
PENDING_SECURITY_PRIVACY_CLASSES = frozenset(
    {
        "local_candidate_pending_security_admission",
        "pending_security_admission",
    }
)

#: A runtime-bearing registry state projects back to what is actually provable
#: from metadata alone: the model was approved and may exist upstream.
_RUNTIME_STATE_FALLBACK = ModelState.AVAILABLE

#: Free-form registry privacy classes -> this lane's ceiling. An unrecognised
#: class is not guessed; it becomes a gate failure.
PRIVACY_CLASS_MAP: Mapping[str, Privacy] = {
    "public": Privacy.PUBLIC,
    "internal": Privacy.INTERNAL,
    "confidential": Privacy.CONFIDENTIAL,
    "secret": Privacy.SECRET,
    "local_only": Privacy.SECRET,
    "local_private": Privacy.SECRET,
}


@dataclass(frozen=True)
class ProjectionResult:
    model_id: str
    profile: ModelProfile | None
    admission_status: AdmissionStatus
    exclusion_reasons: tuple[str, ...]
    #: Claims the registry made that this lane could not verify.
    unverified_claims: tuple[str, ...] = ()
    #: Fields the registry left empty, preserved as unknown.
    unknown_fields: tuple[str, ...] = ()
    #: The first-load contract, carried through from the record's evidence so
    #: the loader cannot lose it between projection and load.
    first_load_isolation_required: bool = True
    first_load_egress_allowed: bool = False

    @property
    def admitted(self) -> bool:
        return self.admission_status is AdmissionStatus.ADMITTED

    @property
    def placeable(self) -> bool:
        """ADMITTED or RESTRICTED - anything that may be considered at all."""
        return self.admission_status is not AdmissionStatus.INELIGIBLE

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "admission_status": self.admission_status.value,
            "exclusion_reasons": list(self.exclusion_reasons),
            "unverified_claims": list(self.unverified_claims),
            "unknown_fields": list(self.unknown_fields),
            "acquisition_eligible": bool(self.profile and self.profile.acquisition_eligible),
            "first_load_isolation_required": self.first_load_isolation_required,
            "first_load_egress_allowed": self.first_load_egress_allowed,
        }


def _gb_to_mb(value: Any) -> int | None:
    """Registry gigabytes -> megabytes. Unknown stays unknown."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value) * _GB_TO_MB))
    except (TypeError, ValueError):
        return None


# -- gates -----------------------------------------------------------------
#
# Each returns a refusal sentence, or None. They are ordered so the most
# fundamental failure is reported first, but all of them run - a caller fixing
# a row wants the whole list, not a game of whack-a-mole.


def _gate_authority(record: Mapping[str, Any]) -> str | None:
    if record.get("authority") is not False:
        return "record claims authority; a registry row is metadata and holds none"
    return None


def _gate_identity(record: Mapping[str, Any]) -> str | None:
    if not str(record.get("model_id") or "").strip():
        return "model_id is missing"
    return None


def _gate_revision(record: Mapping[str, Any]) -> str | None:
    revision = str(record.get("immutable_revision") or record.get("upstream_revision") or "").strip()
    if not revision:
        return "upstream_revision is missing: a model cannot be pinned"
    if revision.lower() in FLOATING_REVISIONS:
        return f"upstream_revision {revision!r} is a floating ref, not a pinned revision"
    return None


def _gate_license(record: Mapping[str, Any]) -> str | None:
    if record.get("license_verified") is not True:
        return "license_verified is not true: licence has not been reviewed"
    license_class = str(record.get("license_class") or "unclear")
    if license_class in BLOCKING_LICENSE_CLASSES:
        return f"license_class {license_class!r} does not permit placement"
    return None


def _gate_zero_cost(record: Mapping[str, Any]) -> str | None:
    if record.get("paid_token_required") is True:
        return "paid_token_required is true; there is no paid fallback"
    cost_class = str(record.get("cost_class") or "unknown")
    if cost_class not in ZERO_COST_CLASSES:
        return f"cost_class {cost_class!r} is not a proven zero-paid-token class"
    return None


def _gate_self_hostable(record: Mapping[str, Any]) -> str | None:
    if record.get("local_runtime_possible") is not True:
        return "local_runtime_possible is not true: this lane runs models locally"
    if record.get("self_hostable") is not True:
        return "self_hostable is not true"
    return None


def _gate_privacy_pending(record: Mapping[str, Any]) -> str | None:
    privacy_class = str(record.get("privacy_class") or "").strip().lower()
    if privacy_class in PENDING_SECURITY_PRIVACY_CLASSES:
        return (
            f"privacy_class {privacy_class!r} marks this a local candidate pending security "
            "admission; it is not cleared for use"
        )
    return None


def _gate_health(record: Mapping[str, Any]) -> str | None:
    health = str(record.get("health") or "unknown")
    if health in {"broken", "blocked"}:
        return f"health is {health!r}"
    return None


def _gate_runtime_support(record: Mapping[str, Any]) -> str | None:
    support = record.get("runtime_support") or []
    if not support:
        return "runtime_support is empty: no runtime can load this artifact"
    if not any(name in RUNTIME_NAME_MAP for name in support):
        return f"runtime_support {sorted(support)} contains no runtime this lane can address"
    return None


def _gate_privacy(record: Mapping[str, Any]) -> str | None:
    privacy_class = str(record.get("privacy_class") or "").strip().lower()
    if not privacy_class:
        return "privacy_class is missing"
    if privacy_class in PENDING_SECURITY_PRIVACY_CLASSES:
        # Understood, and understood to mean not-yet-cleared. Reported by
        # `_gate_privacy_pending`; repeating it here as "unrecognised" would
        # blur a known pending state into an unknown one.
        return None
    if privacy_class not in PRIVACY_CLASS_MAP:
        return f"privacy_class {privacy_class!r} has no mapping; it is not guessed"
    return None


def _gate_mesh_eligibility(record: Mapping[str, Any]) -> str | None:
    """The Model Mesh decides candidacy; this lane only refuses to override it."""
    if record.get("model_mesh_local_candidate_eligible") is False:
        return "model_mesh_local_candidate_eligible is false; the mesh has not nominated this model"
    return None


GATES: tuple[Callable[[Mapping[str, Any]], str | None], ...] = (
    _gate_identity,
    _gate_authority,
    _gate_revision,
    _gate_license,
    _gate_zero_cost,
    _gate_self_hostable,
    _gate_health,
    _gate_runtime_support,
    _gate_privacy_pending,
    _gate_privacy,
    _gate_mesh_eligibility,
)


def _hardware_refusals(record: Mapping[str, Any], snapshot: ResourceSnapshot | None) -> tuple[str, ...]:
    """Refuse a model this machine could not host even when empty.

    Checked against *total* capacity, not free: a model that does not fit an
    idle machine will never fit a busy one, and that is a permanent exclusion
    rather than a scheduling decision.
    """
    if snapshot is None:
        return ()
    hardware = record.get("hardware_profile") or {}
    refusals: list[str] = []

    minimum_ram_mb = _gb_to_mb(hardware.get("minimum_ram_gb"))
    if minimum_ram_mb is not None and snapshot.ram_total_mb is not None:
        if minimum_ram_mb > snapshot.ram_total_mb:
            refusals.append(
                f"needs {minimum_ram_mb} MB RAM; this host has {snapshot.ram_total_mb} MB in total"
            )

    minimum_vram_mb = _gb_to_mb(hardware.get("minimum_vram_gb"))
    cpu_viable = Tri.of(hardware.get("cpu_viable"))
    if minimum_vram_mb:
        installed = max((gpu.vram_total_mb or 0) for gpu in snapshot.gpus) if snapshot.gpus else 0
        if minimum_vram_mb > installed and not cpu_viable.is_true:
            detail = "no GPU is present" if not snapshot.gpus else f"the largest device has {installed} MB"
            refusals.append(
                f"needs {minimum_vram_mb} MB VRAM and is not proven CPU-viable; {detail}"
            )
    return tuple(refusals)


def _select_runtime(record: Mapping[str, Any], available_runtimes: Sequence[str] | None) -> str | None:
    """Pick a runtime the model supports and this host can actually offer."""
    supported = [RUNTIME_NAME_MAP[name] for name in record.get("runtime_support") or [] if name in RUNTIME_NAME_MAP]
    if not supported:
        return None
    if available_runtimes is None:
        return supported[0]
    for name in supported:
        if name in available_runtimes:
            return name
    return None


def _default_policy() -> AdmissionPolicy:
    return load_admission_policy(Path(__file__).resolve().parents[3])


def project_record(
    record: Mapping[str, Any],
    *,
    snapshot: ResourceSnapshot | None = None,
    available_runtimes: Sequence[str] | None = None,
    policy: AdmissionPolicy | None = None,
) -> ProjectionResult:
    """Project one registry row. Never raises, never fabricates.

    Governance clearance is read from `admission_policy.yaml` and the record's
    own `admission_evidence`. Nothing here can mark a model cleared; it can only
    observe that governance already did.
    """
    policy = policy or _default_policy()
    model_id = str(record.get("model_id") or "<unidentified>")
    reasons: list[str] = []
    unverified: list[str] = []
    unknown: list[str] = []

    evidence = record.get("admission_evidence")
    # The older schema used a list of provenance URLs here. That carries no
    # clearance at all, so it is treated as absent rather than as consent.
    structured_evidence = evidence if isinstance(evidence, Mapping) else None

    governance_refusal = policy.governance_refusal(record.get("lifecycle_state"))
    if governance_refusal:
        reasons.append(governance_refusal)
    reasons.extend(policy.evidence_refusals(structured_evidence))
    reasons.extend(policy.identity_refusals(record.get(policy.artifact_identity_source)))

    for gate in GATES:
        try:
            refusal = gate(record)
        except Exception as exc:  # noqa: BLE001 - a malformed row is a refusal, not a crash
            refusal = f"gate {gate.__name__} could not read the record: {type(exc).__name__}: {exc}"
        if refusal:
            reasons.append(refusal)

    reasons.extend(_hardware_refusals(record, snapshot))

    registry_state = str(record.get("lifecycle_state") or "")
    if registry_state_is_runtime_bearing(registry_state):
        unverified.append(
            f"registry claims runtime state {registry_state}; runtime state is observed here, "
            f"not read from metadata, so it projects to {_RUNTIME_STATE_FALLBACK.value}"
        )

    runtime = _select_runtime(record, available_runtimes)
    if runtime is None and not any("runtime_support" in reason for reason in reasons):
        reasons.append(
            "no supported runtime is available on this host"
            if available_runtimes is not None
            else "runtime_support could not be mapped"
        )

    isolation_required = True
    egress_allowed = False
    if structured_evidence is not None:
        isolation_required = bool(structured_evidence.get("isolated_first_load_required", True))
        egress_allowed = bool(structured_evidence.get("first_load_egress_allowed", False))
    if policy.isolated_first_load_if_required and structured_evidence is None:
        isolation_required = True
    if policy.deny_first_load_egress_when_disallowed and not egress_allowed:
        egress_allowed = False

    if reasons:
        return ProjectionResult(
            model_id=model_id,
            profile=None,
            admission_status=AdmissionStatus.INELIGIBLE,
            exclusion_reasons=tuple(dict.fromkeys(reasons)),
            unverified_claims=tuple(unverified),
            unknown_fields=tuple(unknown),
            first_load_isolation_required=isolation_required,
            first_load_egress_allowed=egress_allowed,
        )

    hardware = record.get("hardware_profile") or {}
    minimum_ram_mb = _gb_to_mb(hardware.get("minimum_ram_gb"))
    minimum_vram_mb = _gb_to_mb(hardware.get("minimum_vram_gb"))
    if minimum_ram_mb is None:
        unknown.append("hardware_profile.minimum_ram_gb")
    if hardware.get("minimum_vram_gb") is None:
        unknown.append("hardware_profile.minimum_vram_gb")
    if record.get("context_window") is None:
        unknown.append("context_window")

    # Artifact identity is the acquisition gate, and it is separate from
    # admission: a model whose weights are already cached is perfectly usable
    # without it. The current registry schema carries no checksum or size
    # field at all, so today every row lands here.
    artifact = artifact_block(record)
    artifact_hash = artifact.get("sha256")
    artifact_size = artifact.get("size_bytes")
    acquisition_reasons: list[str] = []
    if not artifact_hash:
        acquisition_reasons.append("artifact hash is absent; a download could not be verified")
        unknown.append("artifact_hash")
    if artifact_size is None:
        acquisition_reasons.append("artifact size is absent; a download could not be budgeted")
        unknown.append("artifact_size_bytes")

    capabilities = record.get("capabilities") or {}
    profile = ModelProfile(
        model_id=model_id,
        ram_mb=minimum_ram_mb,
        vram_mb=minimum_vram_mb,
        disk_mb=None if artifact_size is None else int(artifact_size) // (1024 * 1024),
        runtime=runtime,
        context_limit=record.get("context_window"),
        quality=None,
        quality_class=record.get("quality_class"),
        capabilities=frozenset(capabilities),
        specializations=frozenset(name for name, score in capabilities.items() if score >= 0.8),
        zero_cost=True,
        local=True,
        max_privacy=PRIVACY_CLASS_MAP[str(record["privacy_class"]).strip().lower()],
        family=record.get("family"),
        variant=record.get("variant"),
        revision=record.get("immutable_revision") or record.get("upstream_revision"),
        artifact_hash=artifact_hash,
        artifact_size_bytes=artifact_size,
        quantization=artifact.get("quantization") or record.get("quantization"),
        runtime_support=frozenset(
            RUNTIME_NAME_MAP[name] for name in record.get("runtime_support") or [] if name in RUNTIME_NAME_MAP
        ),
        recommended_ram_mb=_gb_to_mb(hardware.get("recommended_ram_gb")),
        recommended_vram_mb=_gb_to_mb(hardware.get("recommended_vram_gb")),
        cpu_viable=Tri.of(hardware.get("cpu_viable")),
        gpu_viable=Tri.of(bool(minimum_vram_mb) if hardware.get("minimum_vram_gb") is not None else None),
        apple_silicon_viable=Tri.of(hardware.get("apple_silicon_viable")),
        license_verified=True,
        health=str(record.get("health") or "unknown"),
        admission_status=AdmissionStatus.RESTRICTED if acquisition_reasons else AdmissionStatus.ADMITTED,
        acquisition_eligible=not acquisition_reasons,
        exclusion_reasons=tuple(acquisition_reasons),
    )
    return ProjectionResult(
        model_id=model_id,
        profile=profile,
        admission_status=profile.admission_status,
        exclusion_reasons=tuple(acquisition_reasons),
        unverified_claims=tuple(unverified),
        unknown_fields=tuple(dict.fromkeys(unknown)),
        first_load_isolation_required=isolation_required,
        first_load_egress_allowed=egress_allowed,
    )


def load_registry(root: Path) -> Mapping[str, Any]:
    """Read the canonical registry. Read-only; never written by this lane."""
    import yaml

    path = Path(root) / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a mapping")
    return payload


def project_registry(
    registry: Mapping[str, Any],
    *,
    snapshot: ResourceSnapshot | None = None,
    available_runtimes: Sequence[str] | None = None,
    policy: AdmissionPolicy | None = None,
) -> tuple[ProjectionResult, ...]:
    """Project every row. An empty registry projects to an empty tuple."""
    policy = policy or _default_policy()
    models = registry.get("models") or []
    return tuple(
        project_record(
            record, snapshot=snapshot, available_runtimes=available_runtimes, policy=policy
        )
        for record in models
        if isinstance(record, Mapping)
    )
