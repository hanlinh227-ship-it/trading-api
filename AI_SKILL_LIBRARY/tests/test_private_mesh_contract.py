import os
import unittest

import yaml


CONTRACT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "v4",
    "local_runtime",
    "private_mesh.yaml",
)


class PrivateMeshContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CONTRACT_PATH, "r", encoding="utf-8") as handle:
            cls.contract = yaml.safe_load(handle)

    def test_contract_loads_as_mapping(self):
        self.assertIsInstance(self.contract, dict)

    def test_supported_backends(self):
        backends = self.contract.get("supported_backends")
        self.assertEqual(sorted(backends), ["headscale", "tailscale"])

    def test_default_backend_is_supported(self):
        self.assertIn(self.contract.get("default_backend"), self.contract["supported_backends"])

    def test_headscale_is_provider_neutral_escape(self):
        self.assertEqual(self.contract.get("provider_neutral_escape_backend"), "headscale")
        vendor = self.contract.get("vendor_neutrality", {})
        self.assertTrue(vendor.get("headscale_is_provider_neutral_self_hosted_escape_contract"))

    def test_membership_never_implies_admission_or_authority(self):
        membership = self.contract.get("membership_semantics", {})
        for key in (
            "network_membership_implies_worker_admission",
            "network_membership_implies_attestation",
            "network_membership_implies_eligibility",
            "network_membership_implies_capability",
            "network_membership_implies_privacy_permission",
            "network_membership_implies_routing_eligibility",
            "network_membership_implies_execution_authority",
        ):
            self.assertIs(membership.get(key), False, key)

    def test_same_host_aliases_are_not_independent_paths(self):
        aliases = self.contract.get("same_host_aliases", {})
        self.assertIs(
            aliases.get("separate_mesh_identities_count_as_independent_execution_paths"),
            False,
        )

    def test_all_authority_flags_false(self):
        flags = self.contract.get("authority_flags", {})
        for key in (
            "routing_authority",
            "scheduling_authority",
            "worker_admission_authority",
            "model_selection_authority",
            "trading_authority",
        ):
            self.assertIs(flags.get(key), False, key)

    def test_privacy_free_only_outranks_capacity_and_connectivity(self):
        precedence = self.contract.get("policy_precedence", {})
        self.assertTrue(
            precedence.get("privacy_free_only_policy_outranks_capacity_and_connectivity")
        )

    def test_no_vendor_dependency_becomes_authority(self):
        vendor = self.contract.get("vendor_neutrality", {})
        self.assertIs(vendor.get("vendor_dependency_may_become_authority"), False)

    def test_no_new_authoritative_components(self):
        forbidden = self.contract.get("forbidden_components", {})
        for key in (
            "creates_worker_registry",
            "creates_router",
            "creates_scheduler",
            "creates_provider_registry",
            "creates_model_selector",
        ):
            self.assertIs(forbidden.get(key), False, key)

    def test_fail_closed_on_unknown_backend(self):
        fail_closed = self.contract.get("fail_closed", {})
        self.assertTrue(fail_closed.get("unknown_backend_rejected"))
        self.assertEqual(fail_closed.get("on_unknown_backend"), "reject")
        self.assertNotIn("unknown", self.contract["supported_backends"])

    def test_fail_closed_on_implied_automatic_worker_admission(self):
        fail_closed = self.contract.get("fail_closed", {})
        self.assertTrue(
            fail_closed.get("configuration_implying_automatic_worker_admission_rejected")
        )
        self.assertEqual(fail_closed.get("on_implied_automatic_worker_admission"), "reject")

    def test_connectivity_is_transport_only(self):
        self.assertEqual(self.contract.get("status"), "non_authoritative_transport_only")


if __name__ == "__main__":
    unittest.main()
