"""B6: runtime seam against the current canonical contract.

The canonical registry moved artifact identity into `artifact_identity`, turned
`admission_evidence` from a list of URLs into a structured evidence mapping, and
added `admission_policy.yaml` as the gate. These tests pin the runtime side of
that boundary.

The load-bearing assertion throughout: the runtime **consumes** clearance and
never manufactures it. The one row on main is `QUARANTINED` with
`malware_scan_status: not_run`, and every path through this lane must refuse it
while still reading its identity losslessly.
"""

import copy
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.local_runtime.admission_policy import (
    AdmissionPolicy,
    PolicyRelaxationError,
    load_admission_policy,
)
from AI_SKILL_LIBRARY.v4.local_runtime.identity import from_record
from AI_SKILL_LIBRARY.v4.local_runtime.projection import (
    PENDING_SECURITY_PRIVACY_CLASSES,
    project_record,
    project_registry,
)
from AI_SKILL_LIBRARY.v4.local_runtime.residency import admit_to_residency
from AI_SKILL_LIBRARY.v4.local_runtime.resources import HostFacts, ResourceSnapshot
from AI_SKILL_LIBRARY.v4.local_runtime.scheduler import AdmissionStatus

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"

# Canonical values, asserted against the file rather than trusted from anywhere.
CANON_SHA = "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031"
CANON_REV = "1eaf4d9657fe65ad10a51eab76a8db5b363bddaa"
CANON_SIZE = 639446688

HOST = HostFacts(system="Linux", machine="x86_64", release="6.8.0")


def snapshot():
    return ResourceSnapshot(
        host=HOST, cpu_logical=8, cpu_physical=4, ram_total_mb=16_000,
        ram_available_mb=8_000, disk_total_mb=200_000, disk_free_mb=30_000, gpus=(),
    )


def canonical_registry():
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def canonical_record():
    return copy.deepcopy(canonical_registry()["models"][0])


def cleared_record(**overrides):
    """The canonical row with every gate satisfied - a hypothetical future.

    Used only to prove the seam works once governance actually clears the
    model. Nothing here is written back to the registry.
    """
    record = canonical_record()
    record["lifecycle_state"] = "AVAILABLE"
    record["privacy_class"] = "local_only"
    record["model_mesh_local_candidate_eligible"] = True
    record["admission_evidence"].update(
        malware_scan_status="pass",
        quarantine_status="clear",
    )
    record.update(overrides)
    return record


class CanonicalIdentityTests(unittest.TestCase):
    """Nested `artifact_identity` must round-trip losslessly."""

    def test_the_registry_row_carries_artifact_identity(self):
        record = canonical_record()
        self.assertIn("artifact_identity", record)
        self.assertNotIn("artifact", record)

    def test_identity_round_trips_from_artifact_identity(self):
        identity, reasons = from_record(canonical_record())
        self.assertIsNotNone(identity, reasons)
        self.assertEqual(identity.model_id, "Qwen/Qwen3-0.6B-GGUF")
        self.assertEqual(identity.family, "Qwen3")
        self.assertEqual(identity.variant, "0.6B-Q8_0-GGUF")
        self.assertEqual(identity.immutable_revision, CANON_REV)
        self.assertEqual(identity.artifact_sha256, CANON_SHA)
        self.assertEqual(identity.artifact_size_bytes, CANON_SIZE)
        self.assertEqual(identity.artifact_format, "gguf")
        self.assertEqual(identity.quantization, "Q8_0")

    def test_every_policy_required_identity_field_survives(self):
        policy = load_admission_policy(ROOT)
        identity, _ = from_record(canonical_record())
        payload = identity.to_dict()
        alias = {"immutable_revision": "immutable_revision", "sha256": "artifact_sha256",
                 "size_bytes": "artifact_size_bytes", "format": "artifact_format"}
        for field in policy.artifact_identity_required_fields:
            with self.subTest(field=field):
                self.assertTrue(payload.get(alias.get(field, field)), field)

    def test_identity_is_not_mutated_by_projection(self):
        record = canonical_record()
        before = copy.deepcopy(record["artifact_identity"])
        project_record(record, snapshot=snapshot(), available_runtimes=["llama.cpp"])
        self.assertEqual(record["artifact_identity"], before)

    def test_a_cleared_record_projects_the_exact_canonical_identity(self):
        result = project_record(cleared_record(), snapshot=snapshot(),
                                available_runtimes=["llama.cpp"])
        self.assertIsNotNone(result.profile, result.exclusion_reasons)
        profile = result.profile
        self.assertEqual(profile.revision, CANON_REV)
        self.assertEqual(profile.artifact_hash, CANON_SHA)
        self.assertEqual(profile.artifact_size_bytes, CANON_SIZE)
        self.assertEqual(profile.quantization, "Q8_0")
        self.assertEqual(profile.family, "Qwen3")
        self.assertEqual(profile.variant, "0.6B-Q8_0-GGUF")

    def test_identity_drift_between_top_level_and_block_is_refused(self):
        record = canonical_record()
        record["upstream_revision"] = "f" * 40
        identity, reasons = from_record(record)
        self.assertIsNone(identity)
        self.assertTrue(any("disagree" in reason for reason in reasons), reasons)


class QuarantineTests(unittest.TestCase):
    """QUARANTINED stays non-placeable and non-resident, whatever else is true."""

    def test_the_canonical_row_is_quarantined_on_main(self):
        record = canonical_record()
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")
        self.assertEqual(record["admission_evidence"]["quarantine_status"], "quarantined")
        self.assertIs(record["model_mesh_local_candidate_eligible"], False)

    def test_a_quarantined_row_is_never_projected(self):
        result = project_record(canonical_record(), snapshot=snapshot(),
                                available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertIsNone(result.profile)
        self.assertTrue(result.exclusion_reasons)

    def test_the_whole_canonical_registry_projects_to_no_candidate(self):
        results = project_registry(canonical_registry(), snapshot=snapshot(),
                                   available_runtimes=["llama.cpp"])
        self.assertTrue(results)
        self.assertEqual([r for r in results if r.placeable], [])

    def test_a_quarantined_row_cannot_obtain_residency(self):
        decision = admit_to_residency(
            "QUARANTINED", artifact_admitted=True, runtime_eligible=True
        )
        self.assertFalse(decision.granted)
        self.assertIsNone(decision.state)

    def test_every_blocked_state_refuses_projection(self):
        policy = load_admission_policy(ROOT)
        for state in policy.blocked_states:
            with self.subTest(state=state):
                result = project_record(cleared_record(lifecycle_state=state),
                                        snapshot=snapshot(), available_runtimes=["llama.cpp"])
                self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)

    def test_approved_alone_is_not_enough_under_the_current_policy(self):
        # The policy requires AVAILABLE and lists APPROVED as blocked. Runtime
        # follows the policy file, not an older assumption about APPROVED.
        result = project_record(cleared_record(lifecycle_state="APPROVED"),
                                snapshot=snapshot(), available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)

    def test_the_runtime_never_rewrites_governance_state_to_pass(self):
        record = canonical_record()
        project_record(record, snapshot=snapshot(), available_runtimes=["llama.cpp"])
        self.assertEqual(record["lifecycle_state"], "QUARANTINED")
        self.assertEqual(record["admission_evidence"]["quarantine_status"], "quarantined")


class EvidenceFailClosedTests(unittest.TestCase):
    """Unknown or failed security evidence blocks, it does not warn."""

    def _reasons(self, **evidence):
        record = cleared_record()
        record["admission_evidence"].update(evidence)
        return project_record(record, snapshot=snapshot(),
                              available_runtimes=["llama.cpp"]).exclusion_reasons

    def test_malware_scan_not_run_blocks(self):
        self.assertTrue(any("malware" in r for r in self._reasons(malware_scan_status="not_run")))

    def test_malware_scan_unknown_or_failed_blocks(self):
        for status in ("unknown", "fail", "failed", "error", ""):
            with self.subTest(status=status):
                self.assertTrue(any("malware" in r for r in self._reasons(malware_scan_status=status)))

    def test_only_an_explicit_pass_clears_malware(self):
        self.assertEqual(self._reasons(malware_scan_status="pass"), ())

    def test_quarantine_status_must_be_clear(self):
        for status in ("quarantined", "pending", "unknown", ""):
            with self.subTest(status=status):
                self.assertTrue(any("quarantine" in r for r in self._reasons(quarantine_status=status)))

    def test_unverified_license_or_provenance_blocks(self):
        self.assertTrue(any("license" in r for r in self._reasons(license_verified=False)))
        self.assertTrue(any("provenance" in r for r in self._reasons(provenance_verified=False)))

    def test_unsafe_format_or_pickle_risk_blocks(self):
        self.assertTrue(any("safe_format" in r for r in self._reasons(safe_format_verified=False)))
        self.assertTrue(any("pickle" in r for r in self._reasons(pickle_safe=False)))

    def test_remote_or_custom_code_requirements_block(self):
        self.assertTrue(any("trust_remote_code" in r for r in self._reasons(trust_remote_code_required=True)))
        self.assertTrue(any("custom_code" in r for r in self._reasons(custom_code_required=True)))

    def test_missing_critical_evidence_blocks(self):
        record = cleared_record()
        del record["admission_evidence"]["malware_scan_status"]
        reasons = project_record(record, snapshot=snapshot(),
                                 available_runtimes=["llama.cpp"]).exclusion_reasons
        self.assertTrue(any("malware" in r for r in reasons), reasons)

    def test_an_entirely_absent_evidence_block_blocks(self):
        record = cleared_record()
        del record["admission_evidence"]
        result = project_record(record, snapshot=snapshot(), available_runtimes=["llama.cpp"])
        self.assertEqual(result.admission_status, AdmissionStatus.INELIGIBLE)
        self.assertTrue(result.exclusion_reasons)

    def test_mesh_candidate_ineligibility_is_respected(self):
        reasons = project_record(
            cleared_record(model_mesh_local_candidate_eligible=False),
            snapshot=snapshot(), available_runtimes=["llama.cpp"],
        ).exclusion_reasons
        self.assertTrue(any("model_mesh_local_candidate_eligible" in r for r in reasons), reasons)

    def test_first_load_requirements_are_carried_not_dropped(self):
        result = project_record(cleared_record(), snapshot=snapshot(),
                                available_runtimes=["llama.cpp"])
        self.assertTrue(result.first_load_isolation_required)
        self.assertFalse(result.first_load_egress_allowed)


class PendingSecurityPrivacyTests(unittest.TestCase):
    """`local_candidate_pending_security_admission` is explicit and fail-closed."""

    def test_the_canonical_row_uses_the_pending_class(self):
        self.assertEqual(
            canonical_record()["privacy_class"], "local_candidate_pending_security_admission"
        )

    def test_the_pending_class_is_recognised_not_merely_unmapped(self):
        self.assertIn("local_candidate_pending_security_admission", PENDING_SECURITY_PRIVACY_CLASSES)

    def test_the_pending_class_refuses_with_a_specific_reason(self):
        reasons = project_record(
            cleared_record(privacy_class="local_candidate_pending_security_admission"),
            snapshot=snapshot(), available_runtimes=["llama.cpp"],
        ).exclusion_reasons
        self.assertTrue(any("pending security admission" in r for r in reasons), reasons)
        # Distinguishable from an unrecognised class, which is a different fault.
        self.assertFalse(any("not guessed" in r for r in reasons), reasons)

    def test_an_unrecognised_class_still_refuses_separately(self):
        reasons = project_record(cleared_record(privacy_class="vibes"),
                                 snapshot=snapshot(), available_runtimes=["llama.cpp"]).exclusion_reasons
        self.assertTrue(any("not guessed" in r for r in reasons), reasons)

    def test_the_pending_class_never_maps_to_a_usable_ceiling(self):
        from AI_SKILL_LIBRARY.v4.local_runtime.projection import PRIVACY_CLASS_MAP
        for name in PENDING_SECURITY_PRIVACY_CLASSES:
            self.assertNotIn(name, PRIVACY_CLASS_MAP)


class PolicyConsumptionTests(unittest.TestCase):
    """The policy file is an input. The runtime cannot loosen it."""

    def test_the_policy_loads_from_the_canonical_path(self):
        policy = load_admission_policy(ROOT)
        self.assertEqual(policy.governance_state_required, "AVAILABLE")
        self.assertEqual(policy.malware_scan_status_required, "pass")
        self.assertEqual(policy.quarantine_status_required, "clear")
        self.assertTrue(policy.unknown_critical_evidence_blocks)
        self.assertTrue(policy.runtime_may_not_relax_admission)
        self.assertTrue(policy.runtime_may_not_mutate_artifact_identity)

    def test_the_policy_names_the_artifact_identity_source(self):
        self.assertEqual(load_admission_policy(ROOT).artifact_identity_source, "artifact_identity")

    def test_a_relaxed_policy_is_refused(self):
        canonical = load_admission_policy(ROOT)
        for weaker in (
            {"malware_scan_status_required": "not_run"},
            {"quarantine_status_required": "quarantined"},
            {"unknown_critical_evidence_blocks": False},
            {"governance_state_required": "QUARANTINED"},
        ):
            with self.subTest(weaker=weaker):
                with self.assertRaises(PolicyRelaxationError):
                    canonical.replace_for_test(**weaker).assert_not_relaxed(ROOT)

    def test_dropping_a_blocked_state_is_a_relaxation(self):
        canonical = load_admission_policy(ROOT)
        fewer = canonical.replace_for_test(blocked_states=("BLOCKED",))
        with self.assertRaises(PolicyRelaxationError):
            fewer.assert_not_relaxed(ROOT)

    def test_dropping_a_required_identity_field_is_a_relaxation(self):
        canonical = load_admission_policy(ROOT)
        fewer = canonical.replace_for_test(artifact_identity_required_fields=("model_id",))
        with self.assertRaises(PolicyRelaxationError):
            fewer.assert_not_relaxed(ROOT)

    def test_the_canonical_policy_is_not_a_relaxation_of_itself(self):
        load_admission_policy(ROOT).assert_not_relaxed(ROOT)

    def test_projection_uses_the_policy_rather_than_a_hardcoded_list(self):
        # Every state the policy blocks must be refused, with no extra state
        # silently permitted beyond the one the policy requires.
        policy = load_admission_policy(ROOT)
        permitted = []
        for state in sorted(set(policy.blocked_states) | {policy.governance_state_required}):
            result = project_record(cleared_record(lifecycle_state=state),
                                    snapshot=snapshot(), available_runtimes=["llama.cpp"])
            if result.placeable:
                permitted.append(state)
        self.assertEqual(permitted, [policy.governance_state_required])


class AuthorityTests(unittest.TestCase):
    def test_the_policy_module_claims_no_authority(self):
        policy = load_admission_policy(ROOT)
        self.assertFalse(policy.routing_authority)
        self.assertFalse(policy.reasoning_authority)
        self.assertFalse(policy.runtime_residency_authority)

    def test_the_registry_grants_runtime_residency_to_this_lane_only(self):
        integration = canonical_registry()["integration"]
        self.assertEqual(integration["runtime_residency_contract"]["owner"], "claude_local_runtime")
        self.assertFalse(
            integration["runtime_residency_contract"]["open_model_universe_has_runtime_residency_authority"]
        )
        self.assertEqual(integration["model_selection_authority"], "model_mesh")
        self.assertEqual(integration["routed_by"], "task_router")

    def test_no_new_authority_symbol_is_exported(self):
        import AI_SKILL_LIBRARY.v4.local_runtime.admission_policy as module
        for name in ("task_router", "route_task", "TaskRouter", "ParallelRouter"):
            self.assertFalse(hasattr(module, name))


if __name__ == "__main__":
    unittest.main()
