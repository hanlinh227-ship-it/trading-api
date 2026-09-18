"""Canonical route (B2) tests.

The point of the route is that nothing shortcuts it. Ingress never names a
model, the Model Mesh's own filters decide, and a model the mesh refuses is not
run — even when the artifact is sitting verified in the cache.
"""

import datetime
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.local_runtime.canonical_route import (
    LOCAL_PROVIDER_ID,
    as_mesh_candidate,
    mesh_select,
    route_request,
    run_canonical_route,
)
from AI_SKILL_LIBRARY.v4.local_runtime.projection import load_registry, project_record

ROOT = Path(__file__).resolve().parents[2]
_NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def admitted_candidate():
    registry = load_registry(ROOT)
    record = registry["models"][0]
    projected = project_record(record, available_runtimes=["llama.cpp"])
    if projected.profile is None:
        return None, record
    observed = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    return as_mesh_candidate(projected.profile, record, observed_at=observed), record


class RouterStageTests(unittest.TestCase):
    def test_the_router_names_a_domain_and_skill_never_a_model(self):
        routed = route_request("Explain this and plan the work", root=ROOT)
        self.assertEqual(routed["router"], "task_router")
        self.assertTrue(routed["domain"])
        self.assertTrue(routed["primary_skill"])
        self.assertFalse(routed["model_named_at_ingress"])
        self.assertNotIn("model_id", routed)

    def test_routing_matches_whole_words_not_substrings(self):
        """"The capital of France" must not route to engineering.

        Substring matching did exactly that, because "capital" contains "api".
        """
        routed = route_request("The capital of France is", root=ROOT)
        self.assertEqual(routed["domain"], "core")
        self.assertEqual(routed["primary_skill"], "core_reasoning")

    def test_an_unknown_domain_hint_is_ignored_rather_than_trusted(self):
        routed = route_request("hello", root=ROOT, domain_hint="not_a_domain")
        self.assertEqual(routed["domain"], "core")

    def test_a_valid_domain_hint_is_honoured(self):
        routed = route_request("hello", root=ROOT, domain_hint="engineering")
        self.assertEqual(routed["domain"], "engineering")


class MeshCandidateTests(unittest.TestCase):
    def test_the_candidate_uses_the_mesh_vocabulary(self):
        """Values outside the mesh enums normalise to "unknown" and get rejected."""
        candidate, _ = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        self.assertEqual(candidate["privacy_class"], "confidential_safe")
        self.assertEqual(candidate["usage_terms"], "evaluation")
        self.assertNotEqual(candidate["privacy_class"], "unknown")
        self.assertNotEqual(candidate["usage_terms"], "unknown")

    def test_a_local_model_is_offered_as_owned_hardware_zero_marginal(self):
        candidate, _ = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        self.assertEqual(candidate["provider_id"], LOCAL_PROVIDER_ID)
        self.assertTrue(candidate["zero_cost"]["price_verified_at"])

    def test_it_clears_the_free_only_gate(self):
        from AI_SKILL_LIBRARY.v4.tools import model_mesh as mesh
        candidate, _ = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        self.assertTrue(mesh.eligible_free_candidate(candidate, data_class="PUBLIC"))

    def test_selection_explains_every_rejection(self):
        candidate, _ = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        winner, rejections = mesh_select(
            [candidate], domain="core", primary_skill="core_reasoning"
        )
        if winner is None:
            self.assertTrue(rejections)
            self.assertTrue(all(":" in item for item in rejections))

    def test_an_unmeasured_capability_is_refused_by_the_mesh(self):
        """The gate that blocked B2, now asserted as a rule rather than a state.

        This used to read the live registry row and skip itself once the
        capability had been measured. That was right while the measurement was
        the open question, and wrong the moment it was answered: a test that
        skips forever after the thing it guards changes is not guarding it any
        more. So it builds its own unmeasured record and checks the rule, which
        holds whatever the live row happens to say today.
        """
        candidate, record = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")

        unmeasured = dict(record)
        unmeasured["capabilities"] = {"text_reasoning": 0.9}
        unmeasured.pop("capability_evidence", None)

        profile = project_record(record).profile
        projected = as_mesh_candidate(profile, unmeasured, observed_at=_NOW)

        # Score alone is not enough: without evidence the capability cannot be
        # marked supported, and the floor requires supported to be True. A high
        # number with nothing behind it buys nothing.
        self.assertEqual(projected["capabilities"]["text_reasoning"]["score"], 0.9)
        self.assertEqual(projected["capabilities"]["text_reasoning"]["supported"], "unknown")

        winner, rejections = mesh_select(
            [projected], domain="core", primary_skill="core_reasoning"
        )
        self.assertIsNone(winner)
        self.assertTrue(any("capability floor" in item for item in rejections), rejections)

    def test_a_measured_capability_is_supported_and_bound_to_the_artifact(self):
        """Evidence promotes a capability to supported - but only its own.

        The measurement carries the digest of the bytes it was measured on. If
        that digest does not match the record's artifact, the evidence belongs
        to different weights and must not lift this candidate.
        """
        candidate, record = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        if not (record.get("capability_evidence") or {}).get("text_reasoning"):
            self.skipTest("live row carries no measurement to check")

        profile = project_record(record).profile
        measured = as_mesh_candidate(profile, record, observed_at=_NOW)
        row = measured["capabilities"]["text_reasoning"]
        self.assertIs(row["supported"], True)
        self.assertTrue(any(item.startswith("measured:") for item in row["evidence"]), row)

        # Same score, evidence from other bytes -> back to unknown.
        foreign = dict(record)
        foreign["capability_evidence"] = {
            "text_reasoning": {
                **record["capability_evidence"]["text_reasoning"],
                "artifact_sha256": "0" * 64,
            }
        }
        drifted = as_mesh_candidate(profile, foreign, observed_at=_NOW)
        self.assertEqual(drifted["capabilities"]["text_reasoning"]["supported"], "unknown")


class RouteIntegrityTests(unittest.TestCase):
    def test_the_route_stops_where_the_mesh_stops(self):
        result = run_canonical_route(
            "The capital of France is", root=ROOT, cache=ROOT / ".model-cache", max_tokens=8
        )
        stages = {s.stage: s for s in result.stages}
        self.assertTrue(stages["ingress"].ok)
        self.assertTrue(stages["task_router"].ok)
        if not result.ok:
            # A refusal must be attributed to a stage, never silent.
            failed = [s for s in result.stages if not s.ok]
            self.assertEqual(len(failed), 1)
            self.assertIn(failed[0].stage, result.reason)
            self.assertIsNone(result.output)

    def test_no_output_is_produced_when_a_gate_refuses(self):
        result = run_canonical_route(
            "The capital of France is", root=ROOT, cache=ROOT / ".model-cache", max_tokens=8
        )
        if not result.ok:
            self.assertIsNone(result.output)
            self.assertIsNone(result.to_dict()["execution_evidence"])

    def test_the_result_restates_the_authority_split(self):
        payload = run_canonical_route(
            "hello", root=ROOT, cache=ROOT / ".model-cache", max_tokens=4
        ).to_dict()
        self.assertEqual(payload["routing_authority"], "task_router")
        self.assertEqual(payload["model_selection_authority"], "model_mesh")
        self.assertEqual(payload["runtime_residency_authority"], "claude_local_runtime")

    def test_a_missing_cache_fails_at_the_artifact_stage_not_earlier(self):
        import tempfile
        candidate, record = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        declared = (record.get("capabilities") or {}).get("text_reasoning") or 0.0
        if declared <= 0.0:
            self.skipTest("mesh refuses before the artifact stage until capability is measured")
        with tempfile.TemporaryDirectory() as tmp:
            result = run_canonical_route(
                "hello", root=ROOT, cache=Path(tmp), max_tokens=4
            )
        self.assertFalse(result.ok)
        self.assertIn("artifact", result.reason)

    def test_the_route_never_raises(self):
        result = run_canonical_route("x", root=Path("/nonexistent"), cache=Path("/nonexistent"))
        self.assertFalse(result.ok)
        self.assertTrue(result.reason)


if __name__ == "__main__":
    unittest.main()
