"""The role matrix, and the four ways it could quietly lie.

A matrix with a model beside every role looks finished, which is exactly why
these tests spend most of their effort on the cases where it must refuse to
fill a cell: an uncovered role, an unscored model, a tie, and a disagreement
with the canonical coverage record.

Half of these run against synthetic inputs rather than the live evidence. A
test that only reads what happens to be in the repository today passes for
reasons that have nothing to do with the rule it claims to pin.
"""

import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.role_specialization import (
    DEPTH,
    ROLES,
    build,
    rank_role,
)

ROOT = Path(__file__).resolve().parents[2]


def _models(**scores) -> dict:
    """A fleet where each model carries one capability score and a latency."""
    fleet = {}
    for model_id, (capability, score, latency) in scores.items():
        fleet[model_id] = {
            "model_id": model_id,
            "scores": {capability: {"score": score, "passed": int(score * 6),
                                    "attempted": 6, "source": "MEASURED", "suite": "s"}},
            "warm_inference_ms": latency,
        }
    return fleet


class RefusesToFillACellTests(unittest.TestCase):
    """The cells that must stay empty."""

    def test_an_uncovered_role_gets_no_primary(self):
        role = {"role": "AUDIO", "tags": ("audio_understanding",), "suite_key": None}
        tags = {"audio_understanding": {"covered": False, "model": None, "substitute": False,
                                        "blocker_class": "NO_MODEL_IN_VERIFIED_CATALOG",
                                        "wave": 4, "is_a_requirement": True,
                                        "suite_saturated": False}}
        result = rank_role(role, {}, tags)
        self.assertEqual(result["assignments"], [])
        self.assertEqual(result["evidence_class"], "UNCOVERED")

    def test_an_uncovered_role_carries_its_blocker_through_unchanged(self):
        """A restated blocker is a second opinion; this must be the wave's."""
        role = {"role": "AUDIO", "tags": ("audio_understanding",), "suite_key": None}
        tags = {"audio_understanding": {"covered": False, "model": None, "substitute": False,
                                        "blocker_class": "NO_MODEL_IN_VERIFIED_CATALOG",
                                        "wave": 4, "is_a_requirement": True,
                                        "suite_saturated": False}}
        self.assertEqual(rank_role(role, {}, tags)["blocker_class"],
                         "NO_MODEL_IN_VERIFIED_CATALOG")

    def test_a_proven_but_unscored_model_never_holds_primary(self):
        """Reachability is not quality, and this is the cell that confuses them."""
        role = {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"}
        tags = {"deep_reasoning": {"covered": True, "model": None, "substitute": False,
                                   "blocker_class": None, "wave": 5,
                                   "is_a_requirement": True, "suite_saturated": False}}
        hosted = {"REASONING": [{
            "model_id": "@cf/openai/gpt-oss-20b", "score": None,
            "score_source": "EXECUTION_PROVEN_UNSCORED", "score_detail": "200 + completion",
            "suite": None, "warm_inference_ms": None,
            "execution_path": "SERVERLESS_HOSTED_CATALOG", "may_be_primary": False,
        }]}
        result = rank_role(role, {}, tags, hosted)
        self.assertEqual(result["evidence_class"], "PATHS_ONLY_NO_RANKED_OWNER")
        self.assertNotIn("PRIMARY", [row["depth"] for row in result["assignments"]])

    def test_an_unscored_model_does_not_outrank_a_measured_one(self):
        role = {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"}
        tags = {"deep_reasoning": {"covered": True, "model": None, "substitute": False,
                                   "blocker_class": None, "wave": 5,
                                   "is_a_requirement": True, "suite_saturated": False}}
        hosted = {"REASONING": [{
            "model_id": "@cf/hosted", "score": None,
            "score_source": "EXECUTION_PROVEN_UNSCORED", "score_detail": "",
            "suite": None, "warm_inference_ms": None,
            "execution_path": "SERVERLESS_HOSTED_CATALOG", "may_be_primary": False,
        }]}
        fleet = _models(**{"local/weak": ("text_reasoning", 0.4, 100.0)})
        result = rank_role(role, fleet, tags, hosted)
        self.assertEqual(result["assignments"][0]["model_id"], "local/weak")


class MeasuredEvidenceDominatesTests(unittest.TestCase):
    """Which record wins when two records of the same fleet disagree."""

    def _tags(self, named):
        return {"deep_reasoning": {"covered": True, "model": named, "substitute": False,
                                   "blocker_class": None, "wave": 5,
                                   "is_a_requirement": True, "suite_saturated": False}}

    def test_a_measured_score_outranks_the_wave_s_named_model(self):
        role = {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"}
        fleet = _models(**{"a/better": ("text_reasoning", 1.0, 900.0),
                           "b/named": ("text_reasoning", 0.5, 100.0)})
        result = rank_role(role, fleet, self._tags("b/named"))
        self.assertEqual(result["assignments"][0]["model_id"], "a/better")

    def test_the_disagreement_is_reported_rather_than_hidden(self):
        role = {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"}
        fleet = _models(**{"a/better": ("text_reasoning", 1.0, 900.0),
                           "b/named": ("text_reasoning", 0.5, 100.0)})
        differs = rank_role(role, fleet, self._tags("b/named"))["differs_from_wave_coverage"]
        self.assertEqual(differs["wave_named"], "b/named")
        self.assertEqual(differs["this_ordering_picks"], "a/better")

    def test_without_a_measurement_the_wave_s_model_leads(self):
        """The other half: no comparable score means no licence to reorder."""
        role = {"role": "VISION", "tags": ("vision",), "suite_key": None}
        tags = {"vision": {"covered": True, "model": "@cf/llava", "substitute": True,
                           "blocker_class": None, "wave": 4, "is_a_requirement": True,
                           "suite_saturated": False}}
        result = rank_role(role, {}, tags)
        self.assertEqual(result["assignments"][0]["model_id"], "@cf/llava")
        self.assertEqual(result["evidence_class"], "COVERED_UNRANKED")


class TiesAreNamedTests(unittest.TestCase):
    def test_a_tie_is_reported_with_everyone_in_it(self):
        role = {"role": "VERIFICATION", "tags": ("verifier",), "suite_key": "verifier_checker"}
        tags = {"verifier": {"covered": True, "model": None, "substitute": False,
                             "blocker_class": None, "wave": 5, "is_a_requirement": True,
                             "suite_saturated": False}}
        fleet = _models(**{"a/fast": ("verifier_checker", 1.0, 100.0),
                           "b/slow": ("verifier_checker", 1.0, 900.0)})
        tie = rank_role(role, fleet, tags)["tied_at_top"]
        self.assertEqual(tie["models"], ["a/fast", "b/slow"])
        self.assertIn("not a measured quality difference", tie["meaning"])

    def test_a_clear_winner_reports_no_tie(self):
        role = {"role": "VERIFICATION", "tags": ("verifier",), "suite_key": "verifier_checker"}
        tags = {"verifier": {"covered": True, "model": None, "substitute": False,
                             "blocker_class": None, "wave": 5, "is_a_requirement": True,
                             "suite_saturated": False}}
        fleet = _models(**{"a/best": ("verifier_checker", 1.0, 100.0),
                           "b/worse": ("verifier_checker", 0.5, 90.0)})
        self.assertNotIn("tied_at_top", rank_role(role, fleet, tags))


class RedundancyTests(unittest.TestCase):
    def test_emergency_fallback_prefers_a_different_execution_path(self):
        """Four local models is depth on paper; one dead container ends it."""
        role = {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"}
        tags = {"deep_reasoning": {"covered": True, "model": None, "substitute": False,
                                   "blocker_class": None, "wave": 5,
                                   "is_a_requirement": True, "suite_saturated": False}}
        fleet = _models(**{"a/1": ("text_reasoning", 0.9, 100.0),
                           "b/2": ("text_reasoning", 0.8, 200.0),
                           "c/3": ("text_reasoning", 0.7, 300.0),
                           "d/4": ("text_reasoning", 0.6, 400.0)})
        hosted = {"REASONING": [{
            "model_id": "@cf/hosted", "score": None,
            "score_source": "EXECUTION_PROVEN_UNSCORED", "score_detail": "",
            "suite": None, "warm_inference_ms": None,
            "execution_path": "SERVERLESS_HOSTED_CATALOG", "may_be_primary": False,
        }]}
        result = rank_role(role, fleet, tags, hosted)
        last = result["assignments"][-1]
        self.assertEqual(last["depth"], "EMERGENCY_FALLBACK")
        self.assertEqual(last["execution_path"], "SERVERLESS_HOSTED_CATALOG")
        self.assertFalse(result["single_path_risk"])

    def test_one_execution_path_is_flagged_as_a_single_path_risk(self):
        role = {"role": "REASONING", "tags": ("deep_reasoning",), "suite_key": "text_reasoning"}
        tags = {"deep_reasoning": {"covered": True, "model": None, "substitute": False,
                                   "blocker_class": None, "wave": 5,
                                   "is_a_requirement": True, "suite_saturated": False}}
        fleet = _models(**{"a/1": ("text_reasoning", 0.9, 100.0),
                           "b/2": ("text_reasoning", 0.8, 200.0)})
        self.assertTrue(rank_role(role, fleet, tags)["single_path_risk"])


class LiveMatrixTests(unittest.TestCase):
    """What the matrix says about the fleet actually in the repository."""

    @classmethod
    def setUpClass(cls):
        cls.report = build(ROOT)

    def test_it_grants_nothing(self):
        for key in ("routing_authority", "model_selection_authority",
                    "admission_authority", "scheduling_authority"):
            self.assertIs(self.report[key], False, key)

    def test_every_role_in_the_vocabulary_appears(self):
        self.assertEqual(len(self.report["ROLE_CAPABILITY_MATRIX"]), len(ROLES))

    def test_no_assignment_uses_a_depth_outside_the_vocabulary(self):
        for role in self.report["ROLE_CAPABILITY_MATRIX"]:
            for row in role["assignments"]:
                self.assertIn(row["depth"], DEPTH, role["role"])

    def test_no_role_holds_two_models_at_the_same_depth(self):
        for role in self.report["ROLE_CAPABILITY_MATRIX"]:
            depths = [row["depth"] for row in role["assignments"]]
            self.assertEqual(len(depths), len(set(depths)), role["role"])

    def test_no_model_appears_twice_in_one_role(self):
        for role in self.report["ROLE_CAPABILITY_MATRIX"]:
            ids = [row["model_id"] for row in role["assignments"]]
            self.assertEqual(len(ids), len(set(ids)), role["role"])

    def test_uncovered_roles_are_reported_rather_than_dropped(self):
        listed = {row["role"] for row in self.report["UNCOVERED_ROLES"]}
        empty = {role["role"] for role in self.report["ROLE_CAPABILITY_MATRIX"]
                 if not role["assignments"]}
        self.assertEqual(listed, empty)

    def test_every_uncovered_role_names_a_blocker(self):
        for row in self.report["UNCOVERED_ROLES"]:
            self.assertTrue(row["blocker_class"], row["role"])

    def test_no_hosted_unscored_model_holds_a_primary_anywhere(self):
        for role in self.report["ROLE_CAPABILITY_MATRIX"]:
            for row in role["assignments"]:
                if row["depth"] == "PRIMARY":
                    self.assertNotEqual(row.get("score_source"), "EXECUTION_PROVEN_UNSCORED",
                                        role["role"])

    def test_the_residency_matrix_defers_to_the_residency_policy(self):
        for row in self.report["MODEL_RESIDENCY_MATRIX"]:
            self.assertIn(row["residency_authority"],
                          ("local_runtime residency policy", "provider"))


if __name__ == "__main__":
    unittest.main()
