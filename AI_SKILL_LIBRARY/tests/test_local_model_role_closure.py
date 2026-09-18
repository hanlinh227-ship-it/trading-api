"""A flag with nowhere to type the answer in.

unittest-native on purpose, so ci_validate collects it without the pytest
collection gate having to know a count.
"""

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent / "v4" / "tools"
ROOT = _HERE.parent.parent

_spec = importlib.util.spec_from_file_location(
    "local_model_role_closure", _TOOLS / "local_model_role_closure.py")
closure = importlib.util.module_from_spec(_spec)
sys.modules["local_model_role_closure"] = closure
_spec.loader.exec_module(closure)


class VocabularyTests(unittest.TestCase):
    def test_state_tuple_is_derived_from_the_table(self):
        self.assertEqual(closure.ROLE_STATE_VALUES, tuple(closure.ROLE_STATES))

    def test_slot_tuple_is_derived_from_the_precedence_table(self):
        self.assertEqual(
            closure.SLOTS, tuple(slot for slot, _ in closure.SLOT_PRECEDENCE))

    def test_every_slot_maps_to_a_declared_state(self):
        for _, state in closure.SLOT_PRECEDENCE:
            self.assertIn(state, closure.ROLE_STATES)

    def test_there_is_no_override_table(self):
        """The one thing that would make this flag meaningless.

        Walks the module source for any module-level mapping whose name
        suggests a place to write an answer. A flag computed from evidence
        stops being computed the moment somebody can type into it.
        """
        tree = ast.parse((_TOOLS / "local_model_role_closure.py").read_text())
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                self.assertNotIn(
                    "OVERRIDE", name.upper(),
                    "a role override table would make this flag unverifiable")
                self.assertNotIn("MANUAL", name.upper())


class ClassificationTests(unittest.TestCase):
    def test_quarantined_outranks_every_slot(self):
        row = {"lifecycle_state": "QUARANTINED"}
        slots = [{"branch": "B", "slot": "primary"}]
        self.assertEqual(closure.classify(row, slots), "QUARANTINED")

    def test_primary_outranks_a_fallback_elsewhere(self):
        row = {"lifecycle_state": "AVAILABLE"}
        slots = [{"branch": "A", "slot": "fallback"},
                 {"branch": "B", "slot": "primary"}]
        self.assertEqual(closure.classify(row, slots), "PRIMARY")

    def test_emergency_fallback_is_a_fallback(self):
        row = {"lifecycle_state": "AVAILABLE"}
        slots = [{"branch": "A", "slot": "emergency_fallback"}]
        self.assertEqual(closure.classify(row, slots), "FALLBACK")

    def test_no_slot_is_standby(self):
        self.assertEqual(closure.classify({"lifecycle_state": "AVAILABLE"}, []),
                         "STANDBY")

    def test_active_needs_both_registry_signals(self):
        self.assertTrue(closure.is_active(
            {"lifecycle_state": "AVAILABLE",
             "model_mesh_local_candidate_eligible": True}))
        # AVAILABLE but ruled ineligible by the mesh is not the federation
        # failing to use a model.
        self.assertFalse(closure.is_active(
            {"lifecycle_state": "AVAILABLE",
             "model_mesh_local_candidate_eligible": False}))
        self.assertFalse(closure.is_active(
            {"lifecycle_state": "QUARANTINED",
             "model_mesh_local_candidate_eligible": True}))

    def test_a_zero_score_is_not_a_measured_capability(self):
        self.assertFalse(closure.has_measured_capability(
            {"capabilities": {"text_reasoning": 0.0}}))
        self.assertTrue(closure.has_measured_capability(
            {"capabilities": {"text_reasoning": 0.75}}))
        self.assertFalse(closure.has_measured_capability({"capabilities": None}))


class CanonicalEvidenceTests(unittest.TestCase):
    """Run against the repository's own documents, not fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.report = closure.build(ROOT)

    def test_every_admitted_model_lands_in_exactly_one_declared_state(self):
        for row in self.report["models"]:
            self.assertIn(row["role_state"], closure.ROLE_STATES)
        self.assertTrue(self.report["ALL_LOCAL_MODELS_ACCOUNTED_FOR"])

    def test_the_two_quarantined_models_stay_quarantined(self):
        quarantined = {r["model_id"] for r in self.report["models"]
                       if r["role_state"] == "QUARANTINED"}
        self.assertEqual(quarantined, {
            "microsoft/bitnet-b1.58-2B-4T-gguf",
            "mistralai/Ministral-3-3B-Reasoning-2512-GGUF"})
        for row in self.report["models"]:
            if row["role_state"] == "QUARANTINED":
                self.assertFalse(row["active"])

    def test_the_flag_is_computed_and_currently_false(self):
        """granite-3.3-2b is AVAILABLE, mesh-eligible, measured, and unmapped.

        Recorded as a test rather than a note because it is the finding. It
        scores higher on the one measured capability (0.7917) than
        granite-4.2-3b (0.75), which a branch names as a primary. If a future
        run maps it, this test fails and should be rewritten to assert the
        flag is true - it must never be edited to assert true while the
        evidence says otherwise.
        """
        self.assertFalse(self.report["NO_UNMAPPED_ACTIVE_MODEL"])
        unmapped = {r["model_id"] for r in self.report["unmapped_active_models"]}
        self.assertEqual(unmapped, {"ibm-granite/granite-3.3-2b-instruct-GGUF"})

    def test_the_two_mapped_flags_agree_because_they_are_one_fact(self):
        self.assertEqual(self.report["NO_UNMAPPED_ACTIVE_MODEL"],
                         self.report["ALL_ACTIVE_LOCAL_MODELS_ROLE_MAPPED"])

    def test_the_report_claims_no_authority(self):
        for field in ("authority", "routing_authority",
                      "model_selection_authority", "admission_authority"):
            self.assertFalse(self.report[field])
        self.assertTrue(self.report["changes_nothing"])

    def test_the_exit_code_follows_the_flag(self):
        self.assertEqual(closure.main([]), 0 if
                         self.report["NO_UNMAPPED_ACTIVE_MODEL"] else 1)


if __name__ == "__main__":
    unittest.main()
