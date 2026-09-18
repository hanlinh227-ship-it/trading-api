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

    def test_reserve_is_a_fallback_path(self):
        row = {"lifecycle_state": "AVAILABLE"}
        self.assertEqual(
            closure.classify(row, [{"branch": "B", "slot": "reserve"}]), "FALLBACK")

    def test_a_named_slot_outranks_a_reserve_listing(self):
        row = {"lifecycle_state": "AVAILABLE"}
        slots = [{"branch": "A", "slot": "reserve"},
                 {"branch": "B", "slot": "secondary"}]
        self.assertEqual(closure.classify(row, slots), "SECONDARY")

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

    def test_no_active_model_is_left_unmapped(self):
        """Was false; now true, and the reason is a generator fix.

        The previous version of this test asserted the flag was FALSE and said
        that if a future run mapped the model it should be rewritten - but only
        for the right reason, never by editing the assertion to match a wish.
        The right reason arrived: `role_capability_matrix` was drawing four slot
        names from a candidate list of unbounded length, at indices 0, 1, 2 and
        -1, so on REASONING_BRANCH's eight candidates indices 3 through 6 were
        ranked and then discarded. granite-3.3-2b sat at [4] there, [3] on
        VERIFICATION_BRANCH and [4] on VIETNAMESE_BRANCH. Recording those as
        `reserve` moved no model and re-ranked nothing.
        """
        self.assertTrue(self.report["NO_UNMAPPED_ACTIVE_MODEL"])
        self.assertEqual(self.report["unmapped_active_models"], [])

    def test_the_previously_unmapped_model_is_mapped_by_measurement(self):
        row = next(r for r in self.report["models"]
                   if r["model_id"] == "ibm-granite/granite-3.3-2b-instruct-GGUF")
        self.assertEqual(row["role_state"], "FALLBACK")
        self.assertTrue(row["active"])
        self.assertTrue(row["has_measured_capability"])
        # Named by real branches, in the reserve the ranking produced.
        branches = {e["branch"] for e in row["role_slots"]}
        self.assertIn("REASONING_BRANCH", branches)
        self.assertIn("VERIFICATION_BRANCH", branches)
        for entry in row["role_slots"]:
            self.assertIn(entry["slot"], closure.SLOTS)

    def test_nothing_was_demoted_to_make_room(self):
        """The three primaries are the three the ranking already chose."""
        primaries = {r["model_id"] for r in self.report["models"]
                     if r["role_state"] == "PRIMARY"}
        self.assertEqual(primaries, {
            "Qwen/Qwen3-4B-GGUF",
            "Qwen/Qwen3-8B-GGUF",
            "ibm-granite/granite-4.2-3b-GGUF"})

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


def _ids(entries):
    """Model ids from a list that may hold plain strings or candidate dicts.

    `all_candidates` holds strings and `reserve` holds dicts. Assuming dicts
    everywhere made a coverage test iterate an empty list and pass while
    checking nothing.
    """
    out = []
    for entry in entries or []:
        if isinstance(entry, dict) and entry.get("model_id"):
            out.append(str(entry["model_id"]))
        elif isinstance(entry, str) and entry:
            out.append(entry)
    return out


class ReserveSlotTests(unittest.TestCase):
    """The hole between `fallback` and `emergency_fallback`, and its edges."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "role_capability_matrix_under_test",
            _TOOLS / "role_capability_matrix.py")
        cls.rcm = importlib.util.module_from_spec(spec)
        sys.modules["role_capability_matrix_under_test"] = cls.rcm
        spec.loader.exec_module(cls.rcm)
        cls.matrix = cls.rcm.build(ROOT)

    def test_every_ranked_candidate_reaches_a_slot_or_the_reserve(self):
        """The invariant the four names could not state on their own."""
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            ranked = _ids(row.get("all_candidates"))
            self.assertEqual(len(ranked), row.get("candidate_count") or 0,
                             "a coverage check over an empty list proves nothing")
            named = set()
            for slot in ("primary", "secondary", "fallback", "emergency_fallback"):
                entry = row.get(slot)
                if isinstance(entry, dict) and entry.get("model_id"):
                    named.add(entry["model_id"])
            named |= {c["model_id"] for c in (row.get("reserve") or [])}
            missing = [m for m in ranked if m not in named]
            self.assertEqual(
                missing, [],
                "%s ranks these and names them nowhere: %s"
                % (row["role_id"], missing))

    def test_reserve_never_repeats_a_named_slot(self):
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            named = set()
            for slot in ("primary", "secondary", "fallback", "emergency_fallback"):
                entry = row.get(slot)
                if isinstance(entry, dict) and entry.get("model_id"):
                    named.add(entry["model_id"])
            for model_id in _ids(row.get("reserve")):
                self.assertNotIn(model_id, named, row["role_id"])

    def test_reserve_is_empty_when_the_four_names_cover_everything(self):
        """Four or fewer candidates: 0, 1, 2 and -1 leave nothing over."""
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            if (row.get("candidate_count") or 0) <= 4:
                self.assertEqual(row.get("reserve") or [], [], row["role_id"])

    def test_reserve_holds_exactly_the_middle_of_a_longer_ranking(self):
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            count = row.get("candidate_count") or 0
            if count > 4:
                self.assertEqual(len(row["reserve"]), count - 4, row["role_id"])

    def test_reserve_keeps_the_ranking_order(self):
        for row in self.matrix["ROLE_CAPABILITY_MATRIX"]:
            ranked = _ids(row.get("all_candidates"))
            reserved = _ids(row.get("reserve"))
            self.assertEqual(reserved,
                             [m for m in ranked if m in set(reserved)],
                             row["role_id"])
