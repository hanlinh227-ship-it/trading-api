"""Permission to run offline is not evidence of having run offline."""

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent.parent
_TOOLS = ROOT / "AI_SKILL_LIBRARY/v4/tools"

_spec = importlib.util.spec_from_file_location(
    "local_zero_api_fabric", _TOOLS / "local_zero_api_fabric.py")
fabric = importlib.util.module_from_spec(_spec)
sys.modules["local_zero_api_fabric"] = fabric
_spec.loader.exec_module(fabric)


class VocabularyTests(unittest.TestCase):
    def test_tuples_are_derived_from_their_tables(self):
        self.assertEqual(fabric.LICENSE_STATE_VALUES, tuple(fabric.LICENSE_STATES))
        self.assertEqual(fabric.ARTIFACT_PROPERTY_VALUES,
                         tuple(fabric.ARTIFACT_PROPERTIES))

    def test_every_state_carries_a_written_condition(self):
        for table in (fabric.LICENSE_STATES, fabric.ARTIFACT_PROPERTIES):
            for name, why in table.items():
                self.assertGreater(len(why), 20, name)


class LicenseTests(unittest.TestCase):
    BASE = {"license_verified": True, "license_class": "permissive",
            "redistribution": "allowed", "paid_token_required": False}

    def test_a_clean_row_is_accepted(self):
        self.assertEqual(fabric.license_state(dict(self.BASE)), "LICENSE_ACCEPTED")

    def test_a_paid_token_blocks_regardless_of_licence(self):
        row = dict(self.BASE, paid_token_required=True)
        self.assertEqual(fabric.license_state(row), "LICENSE_BLOCKED")

    def test_an_unverified_licence_needs_review(self):
        row = dict(self.BASE, license_verified=False)
        self.assertEqual(fabric.license_state(row), "LICENSE_REVIEW_REQUIRED")

    def test_a_non_permissive_licence_needs_review(self):
        row = dict(self.BASE, license_class="research_only")
        self.assertEqual(fabric.license_state(row), "LICENSE_REVIEW_REQUIRED")

    def test_forbidden_redistribution_needs_review(self):
        row = dict(self.BASE, redistribution="forbidden")
        self.assertEqual(fabric.license_state(row), "LICENSE_REVIEW_REQUIRED")

    def test_a_missing_field_is_never_defaulted_to_the_easy_answer(self):
        # An absent field must not read as "no problem".
        self.assertNotEqual(fabric.license_state({}), "LICENSE_ACCEPTED")


class PropertyTests(unittest.TestCase):
    def test_free_download_is_not_permissive_licence(self):
        """The conflation section 27 asks to be kept apart."""
        row = {"open_weight": True, "paid_token_required": False,
               "license_class": "research_only", "license_verified": True,
               "api_required": False, "runtime_support": ["llama_cpp"]}
        props = fabric.artifact_properties(row)
        self.assertTrue(props["FREE_DOWNLOAD"])
        self.assertFalse(props["PERMISSIVE_LICENSE"])
        self.assertTrue(props["RESTRICTED_LICENSE"])

    def test_an_unknown_runtime_is_not_counted_as_open_source(self):
        row = {"runtime_support": ["some_vendor_sdk"], "open_weight": True,
               "paid_token_required": False, "license_class": "permissive",
               "license_verified": True, "api_required": False}
        self.assertFalse(fabric.artifact_properties(row)["OPEN_SOURCE_RUNTIME"])

    def test_no_runtime_at_all_is_not_open_source(self):
        row = {"runtime_support": [], "open_weight": True,
               "paid_token_required": False, "license_class": "permissive",
               "license_verified": True, "api_required": False}
        self.assertFalse(fabric.artifact_properties(row)["OPEN_SOURCE_RUNTIME"])

    def test_digest_binding_needs_all_three_parts(self):
        full = {"artifact_identity": {"sha256": "a" * 64, "immutable_revision": "r",
                                      "size_bytes": 10}}
        self.assertTrue(fabric.digest_bound(full))
        self.assertFalse(fabric.digest_bound(
            {"artifact_identity": {"sha256": "a" * 63, "immutable_revision": "r",
                                   "size_bytes": 10}}))
        self.assertFalse(fabric.digest_bound(
            {"artifact_identity": {"sha256": "a" * 64, "size_bytes": 10}}))
        self.assertFalse(fabric.digest_bound({"artifact_identity": {}}))
        self.assertFalse(fabric.digest_bound({}))


class CanonicalRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = fabric.build(ROOT)

    def test_no_admitted_model_needs_a_key_or_a_subscription(self):
        self.assertFalse(self.report["LOCAL_API_KEY_REQUIRED"])
        self.assertFalse(self.report["LOCAL_SUBSCRIPTION_REQUIRED"])
        self.assertFalse(self.report["LOCAL_PROVIDER_DEPENDENCY"])

    def test_a_zero_api_path_exists_and_is_named(self):
        self.assertTrue(self.report["LOCAL_ZERO_API_PATH_AVAILABLE"])
        self.assertTrue(self.report["zero_api_usable_models"])

    def test_the_quarantined_pair_is_not_counted_as_usable(self):
        usable = set(self.report["zero_api_usable_models"])
        self.assertNotIn("microsoft/bitnet-b1.58-2B-4T-gguf", usable)
        self.assertNotIn("mistralai/Ministral-3-3B-Reasoning-2512-GGUF", usable)

    def test_every_row_carries_the_fields_this_reads(self):
        self.assertEqual(self.report["rows_with_missing_fields"], [])
        self.assertEqual(self.report["models_read"],
                         self.report["models_in_registry"])

    def test_every_artifact_is_digest_bound(self):
        self.assertTrue(self.report["LOCAL_ARTIFACTS_DIGEST_BOUND"])
        for row in self.report["models"]:
            self.assertTrue(row["immutable_revision"], row["model_id"])


class ClaimsNotMadeTests(unittest.TestCase):
    """The two things this tool must never drift into claiming."""

    def test_offline_execution_is_not_inferred_from_licence_metadata(self):
        report = fabric.build(ROOT)
        self.assertTrue(report["LOCAL_ZERO_API_PATH_AVAILABLE"])
        # Clean metadata everywhere, and still false: permission is not
        # performance, and only a run with egress denied can move this.
        self.assertFalse(report["LOCAL_OFFLINE_EXECUTION_VERIFIED"])
        self.assertIn("no offline run has been recorded",
                      report["offline_execution_blocker"])

    def test_source_permanence_is_never_claimed(self):
        self.assertFalse(fabric.ARTIFACT_SOURCE_PERMANENCE_CLAIMED)
        self.assertFalse(fabric.build(ROOT)["ARTIFACT_SOURCE_PERMANENCE_CLAIMED"])

    def test_the_permanence_note_keeps_the_two_claims_apart(self):
        note = fabric.build(ROOT)["permanence_note"]
        self.assertIn("recurring fee", note)
        self.assertIn("somebody", note)

    def test_the_report_claims_no_authority(self):
        report = fabric.build(ROOT)
        for field in ("authority", "routing_authority", "model_selection_authority"):
            self.assertFalse(report[field])
        self.assertTrue(report["changes_nothing"])


if __name__ == "__main__":
    unittest.main()
