"""Consumer for the canonical admission policy.

`AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml` is the gate
between the Open Model Universe and this lane. It is owned by governance; this
module reads it and applies it, and that asymmetry is the whole design.

Three properties hold by construction.

**The runtime never manufactures clearance.** Every gate answers from a field
the record already carries. There is no path here that marks a model safe,
scanned, licensed or unquarantined - it can only observe that governance
already did.

**Unknown is refusal, not a warning.** `unknown_critical_evidence_blocks` is
true in the canonical policy, and missing evidence is treated identically to
failed evidence. A `malware_scan_status` of `not_run` is not "probably fine".

**The runtime cannot loosen the gate.** `assert_not_relaxed()` re-reads the
canonical file and refuses any in-memory policy weaker than it, on every
dimension: a lowered status requirement, a dropped blocked state, a dropped
required identity field, or `unknown_critical_evidence_blocks` turned off. A
future edit that tries to make a stubborn model pass by softening the policy
object fails a test instead of shipping.

The policy also *tightens* nothing on its own. Where the canonical file says
`governance_state_required: AVAILABLE` and lists `APPROVED` among the blocked
states, this module follows the file rather than an older intuition about what
approval ought to mean.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

POLICY_PATH = "AI_SKILL_LIBRARY/v4/open_model_universe/admission_policy.yaml"

#: Boolean evidence fields and the value each must hold to clear.
_BOOLEAN_GATES: Mapping[str, tuple[str, bool]] = {
    "require_license_verified": ("license_verified", True),
    "require_provenance_verified": ("provenance_verified", True),
    "require_safe_format_verified": ("safe_format_verified", True),
    "require_pickle_safe": ("pickle_safe", True),
    "trust_remote_code_required_must_be": ("trust_remote_code_required", False),
    "custom_code_required_must_be": ("custom_code_required", False),
}


class PolicyRelaxationError(RuntimeError):
    """An in-memory policy weaker than the canonical file on disk."""


@dataclass(frozen=True)
class AdmissionPolicy:
    version: int
    governance_state_required: str
    blocked_states: tuple[str, ...]
    artifact_identity_source: str
    artifact_identity_required_fields: tuple[str, ...]
    malware_scan_status_required: str
    quarantine_status_required: str
    unknown_critical_evidence_blocks: bool
    boolean_gates: Mapping[str, bool]
    isolated_first_load_if_required: bool
    deny_first_load_egress_when_disallowed: bool
    runtime_may_not_relax_admission: bool
    runtime_may_not_mutate_artifact_identity: bool

    #: This module decides nothing about routing or residency; it reports.
    routing_authority = False
    reasoning_authority = False
    runtime_residency_authority = False

    # -- gates -------------------------------------------------------------

    def evidence_refusals(self, evidence: Mapping[str, Any] | None) -> tuple[str, ...]:
        """Why this evidence block does not clear. Empty means it does."""
        if not isinstance(evidence, Mapping):
            return ("admission_evidence is absent; no clearance to consume",)

        refusals: list[str] = []
        for field, expected in self.boolean_gates.items():
            actual = evidence.get(field)
            if actual is None:
                if self.unknown_critical_evidence_blocks:
                    refusals.append(f"admission evidence {field} is absent")
                continue
            if bool(actual) is not expected:
                refusals.append(f"admission evidence {field}={actual!r}; policy requires {expected!r}")

        scan = evidence.get("malware_scan_status")
        if str(scan or "").strip().lower() != self.malware_scan_status_required:
            refusals.append(
                f"malware_scan_status={scan or '<absent>'!r}; "
                f"policy requires {self.malware_scan_status_required!r}"
            )

        quarantine = evidence.get("quarantine_status")
        if str(quarantine or "").strip().lower() != self.quarantine_status_required:
            refusals.append(
                f"quarantine_status={quarantine or '<absent>'!r}; "
                f"policy requires {self.quarantine_status_required!r}"
            )
        return tuple(refusals)

    def governance_refusal(self, lifecycle_state: str | None) -> str | None:
        state = str(lifecycle_state or "").strip().upper()
        if state in self.blocked_states:
            return f"governance state {state} is blocked by the admission policy"
        if state != self.governance_state_required:
            return (
                f"governance state {state or '<absent>'} is not "
                f"{self.governance_state_required}, which the admission policy requires"
            )
        return None

    def identity_refusals(self, identity_block: Mapping[str, Any] | None) -> tuple[str, ...]:
        if not isinstance(identity_block, Mapping):
            return (f"{self.artifact_identity_source} block is absent",)
        return tuple(
            f"{self.artifact_identity_source}.{field} is absent"
            for field in self.artifact_identity_required_fields
            if not str(identity_block.get(field) or "").strip()
        )

    # -- anti-relaxation ---------------------------------------------------

    def replace_for_test(self, **changes: Any) -> "AdmissionPolicy":
        """Build a variant. Named so its only legitimate use is obvious."""
        return replace(self, **changes)

    def assert_not_relaxed(self, root: Path) -> None:
        """Refuse any policy weaker than the canonical file on disk."""
        canonical = load_admission_policy(root)
        if self.governance_state_required != canonical.governance_state_required:
            raise PolicyRelaxationError(
                f"governance_state_required {self.governance_state_required!r} differs from "
                f"canonical {canonical.governance_state_required!r}"
            )
        if self.malware_scan_status_required != canonical.malware_scan_status_required:
            raise PolicyRelaxationError("malware_scan_status_required weakened")
        if self.quarantine_status_required != canonical.quarantine_status_required:
            raise PolicyRelaxationError("quarantine_status_required weakened")
        if canonical.unknown_critical_evidence_blocks and not self.unknown_critical_evidence_blocks:
            raise PolicyRelaxationError("unknown_critical_evidence_blocks disabled")
        missing_states = set(canonical.blocked_states) - set(self.blocked_states)
        if missing_states:
            raise PolicyRelaxationError(f"blocked states dropped: {sorted(missing_states)}")
        missing_fields = set(canonical.artifact_identity_required_fields) - set(
            self.artifact_identity_required_fields
        )
        if missing_fields:
            raise PolicyRelaxationError(f"required identity fields dropped: {sorted(missing_fields)}")
        missing_gates = {
            field for field, expected in canonical.boolean_gates.items()
            if self.boolean_gates.get(field) != expected
        }
        if missing_gates:
            raise PolicyRelaxationError(f"evidence gates weakened: {sorted(missing_gates)}")
        for flag in ("isolated_first_load_if_required", "deny_first_load_egress_when_disallowed",
                     "runtime_may_not_relax_admission", "runtime_may_not_mutate_artifact_identity"):
            if getattr(canonical, flag) and not getattr(self, flag):
                raise PolicyRelaxationError(f"{flag} disabled")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "version": self.version,
            "governance_state_required": self.governance_state_required,
            "blocked_states": list(self.blocked_states),
            "artifact_identity_source": self.artifact_identity_source,
            "artifact_identity_required_fields": list(self.artifact_identity_required_fields),
            "malware_scan_status_required": self.malware_scan_status_required,
            "quarantine_status_required": self.quarantine_status_required,
            "unknown_critical_evidence_blocks": self.unknown_critical_evidence_blocks,
            "boolean_gates": dict(self.boolean_gates),
            "runtime_may_not_relax_admission": self.runtime_may_not_relax_admission,
            "runtime_may_not_mutate_artifact_identity": self.runtime_may_not_mutate_artifact_identity,
            "routing_authority": self.routing_authority,
        }


def _tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def load_admission_policy(root: Path | str) -> AdmissionPolicy:
    """Read the canonical policy. Read-only; this lane never writes it."""
    import yaml

    payload = yaml.safe_load((Path(root) / POLICY_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{POLICY_PATH} is not a mapping")

    gate = payload.get("candidate_gate") or {}
    first_load = payload.get("runtime_first_load_contract") or {}
    boolean_gates = {
        _BOOLEAN_GATES[key][0]: bool(gate.get(key, _BOOLEAN_GATES[key][1]))
        if key.endswith("_must_be")
        else _BOOLEAN_GATES[key][1]
        for key in _BOOLEAN_GATES
        if key in gate
    }
    # `require_*` keys assert True; `*_must_be` keys carry the required value.
    for key, (field, default) in _BOOLEAN_GATES.items():
        if key not in gate:
            continue
        boolean_gates[field] = bool(gate[key]) if key.endswith("_must_be") else default

    return AdmissionPolicy(
        version=int(payload.get("version", 1)),
        governance_state_required=str(gate.get("governance_state_required", "AVAILABLE")),
        blocked_states=_tuple(gate.get("blocked_states")),
        artifact_identity_source=str(payload.get("artifact_identity_source", "artifact_identity")),
        artifact_identity_required_fields=_tuple(payload.get("artifact_identity_required_fields")),
        malware_scan_status_required=str(gate.get("malware_scan_status_required", "pass")).lower(),
        quarantine_status_required=str(gate.get("quarantine_status_required", "clear")).lower(),
        unknown_critical_evidence_blocks=bool(gate.get("unknown_critical_evidence_blocks", True)),
        boolean_gates=boolean_gates,
        isolated_first_load_if_required=bool(first_load.get("isolated_first_load_if_required", True)),
        deny_first_load_egress_when_disallowed=bool(
            first_load.get("deny_first_load_egress_when_first_load_egress_allowed_false", True)
        ),
        runtime_may_not_relax_admission=bool(first_load.get("runtime_may_not_relax_admission", True)),
        runtime_may_not_mutate_artifact_identity=bool(
            first_load.get("runtime_may_not_mutate_artifact_identity", True)
        ),
    )
