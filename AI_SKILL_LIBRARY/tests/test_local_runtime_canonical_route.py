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
        """The gate that currently blocks B2, pinned as correct behaviour.

        The registry declares text_reasoning 0.0 with benchmark_profile
        "unverified". The mesh refuses it, and that refusal is right: a measured
        capability score is benchmark evidence, and inventing one here to make
        the route light up would be fabricating exactly that.
        """
        candidate, record = admitted_candidate()
        if candidate is None:
            self.skipTest("no admitted local candidate")
        declared = (record.get("capabilities") or {}).get("text_reasoning")
        if declared is None or declared > 0.0:
            self.skipTest("capability has since been measured")
        winner, rejections = mesh_select(
            [candidate], domain="core", primary_skill="core_reasoning"
        )
        self.assertIsNone(winner)
        self.assertTrue(any("capability floor" in item for item in rejections), rejections)


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
