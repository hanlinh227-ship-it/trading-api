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

**An operator may accept a risk; they may not rewrite a finding.** Where a
check genuinely cannot run in this environment, the canonical policy permits a
named, digest-bound acceptance for exactly one gate. The underlying evidence
field keeps its true value - `malware_scan_status` stays `not_run` - and the
acceptance travels beside it so nothing downstream can mistake a decision for a
scan. `risk_acceptance_refusals()` validates the acceptance itself: missing
fields, a blanket scope, or a digest that does not match this artifact all
invalidate it.

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
    #: Operator-override configuration, read from the canonical policy.
    risk_acceptance_permitted: bool
    risk_acceptance_may_substitute_for: tuple[str, ...]
    risk_acceptance_never_substitutes_for: tuple[str, ...]
    risk_acceptance_required_fields: tuple[str, ...]
    risk_acceptance_scope_must_be: str
    isolated_first_load_if_required: bool
    deny_first_load_egress_when_disallowed: bool
    runtime_may_not_relax_admission: bool
    runtime_may_not_mutate_artifact_identity: bool

    #: This module decides nothing about routing or residency; it reports.
    routing_authority = False
    reasoning_authority = False
    runtime_residency_authority = False

    # -- gates -------------------------------------------------------------

    def risk_acceptance_refusals(
        self, acceptance: Mapping[str, Any] | None, *, artifact_sha256: str | None
    ) -> tuple[str, ...]:
        """Why this acceptance is not usable. Empty means it is.

        An acceptance is a decision record, so it has to be complete enough to
        audit: who accepted, when, on what basis, what is missing, and which
        exact artifact it covers.
        """
        if acceptance is None:
            return ("no operator risk acceptance supplied",)
        if not self.risk_acceptance_permitted:
            return ("operator risk acceptance is not permitted by the admission policy",)
        if not isinstance(acceptance, Mapping):
            return ("operator_risk_acceptance must be a mapping",)

        refusals = [
            f"operator_risk_acceptance.{field} is absent"
            for field in self.risk_acceptance_required_fields
            if not str(acceptance.get(field) or "").strip()
        ]

        scope = str(acceptance.get("scope") or "").strip()
        if scope and scope != self.risk_acceptance_scope_must_be:
            refusals.append(
                f"operator_risk_acceptance.scope must be {self.risk_acceptance_scope_must_be!r}, "
                f"not {scope!r}; a blanket acceptance is refused"
            )

        # Bound to one artifact by digest, so an acceptance cannot be recycled
        # onto different bytes than the one it was granted for.
        declared = str(acceptance.get("artifact_sha256") or "").strip().lower()
        if declared and artifact_sha256 and declared != str(artifact_sha256).strip().lower():
            refusals.append(
                "operator_risk_acceptance.artifact_sha256 does not match this artifact; "
                "an acceptance is bound to the exact bytes it was granted for"
            )
        if declared and not artifact_sha256:
            refusals.append("cannot confirm the acceptance digest: this record has no artifact sha256")

        covers = [
            str(gate) for gate in (acceptance.get("covers") or self.risk_acceptance_may_substitute_for)
        ]
        forbidden = sorted(set(covers) & set(self.risk_acceptance_never_substitutes_for))
        if forbidden:
            refusals.append(
                f"operator_risk_acceptance may never substitute for {forbidden}"
            )
        outside = sorted(set(covers) - set(self.risk_acceptance_may_substitute_for))
        if outside:
            refusals.append(
                f"operator_risk_acceptance covers {outside}, which the policy does not allow it to"
            )
        return tuple(refusals)

    def accepted_gaps(
        self, acceptance: Mapping[str, Any] | None, *, artifact_sha256: str | None
    ) -> frozenset[str]:
        """Gates a *valid* acceptance covers. Empty when it is not valid."""
        if self.risk_acceptance_refusals(acceptance, artifact_sha256=artifact_sha256):
            return frozenset()
        covers = (acceptance or {}).get("covers") or self.risk_acceptance_may_substitute_for
        return frozenset(str(gate) for gate in covers)

    def evidence_refusals(
        self, evidence: Mapping[str, Any] | None, *, accepted_gaps: frozenset[str] = frozenset()
    ) -> tuple[str, ...]:
        """Why this evidence block does not clear. Empty means it does.

        `accepted_gaps` names gates covered by a validated operator acceptance.
        Only gates the policy allows to be accepted are honoured, so passing a
        forbidden gate here cannot widen anything.
        """
        if not isinstance(evidence, Mapping):
            return ("admission_evidence is absent; no clearance to consume",)

        honoured = frozenset(accepted_gaps) & frozenset(self.risk_acceptance_may_substitute_for)
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
            # An acceptance covers a known *absence* of evidence, never an
            # adverse or ambiguous result. "not_run" is something an operator
            # can knowingly accept; "fail" is a finding and "unknown" means
            # something happened that nobody has explained. Neither is
            # acceptable by decision.
            if "malware_scan_status" in honoured and str(scan or "").strip().lower() == "not_run":
                # Accepted, not satisfied. The field keeps its true value and
                # the decision is recorded; this only stops it blocking.
                pass
            else:
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
        missing_never = set(canonical.risk_acceptance_never_substitutes_for) - set(
            self.risk_acceptance_never_substitutes_for
        )
        if missing_never:
            raise PolicyRelaxationError(
                f"risk-acceptance exclusions dropped: {sorted(missing_never)}"
            )
        widened = set(self.risk_acceptance_may_substitute_for) - set(
            canonical.risk_acceptance_may_substitute_for
        )
        if widened:
            raise PolicyRelaxationError(f"risk acceptance widened to cover: {sorted(widened)}")
        missing_fields_ra = set(canonical.risk_acceptance_required_fields) - set(
            self.risk_acceptance_required_fields
        )
        if missing_fields_ra:
            raise PolicyRelaxationError(
                f"risk-acceptance required fields dropped: {sorted(missing_fields_ra)}"
            )
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
            "risk_acceptance_permitted": self.risk_acceptance_permitted,
            "risk_acceptance_may_substitute_for": list(self.risk_acceptance_may_substitute_for),
            "risk_acceptance_never_substitutes_for": list(self.risk_acceptance_never_substitutes_for),
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

    acceptance = gate.get("operator_risk_acceptance") or {}
    return AdmissionPolicy(
        risk_acceptance_permitted=bool(acceptance.get("permitted", False)),
        risk_acceptance_may_substitute_for=_tuple(acceptance.get("may_substitute_for")),
        risk_acceptance_never_substitutes_for=_tuple(acceptance.get("never_substitutes_for")),
        risk_acceptance_required_fields=_tuple(acceptance.get("required_fields")),
        risk_acceptance_scope_must_be=str(acceptance.get("scope_must_be", "single_artifact")),
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
