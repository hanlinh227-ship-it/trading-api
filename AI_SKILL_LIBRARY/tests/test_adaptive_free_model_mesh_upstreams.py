import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class AdaptiveFreeModelMeshUpstreamTests(unittest.TestCase):
    def _yaml(self, rel: str) -> dict:
        path = ROOT / rel
        self.assertTrue(path.is_file(), rel)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict, rel)
        return data

    def test_policy_is_free_only_and_not_routing_authority(self):
        policy = self._yaml("AI_SKILL_LIBRARY/v4/model_mesh/policy.yaml")
        self.assertEqual(policy["mode"], "FREE_ONLY")
        self.assertFalse(policy["routing_authority"])
        self.assertFalse(policy["reasoning_authority"])
        self.assertEqual(policy["max_parallel"]["FAST"], 0)
        self.assertEqual(policy["max_parallel"]["STANDARD"], 2)
        self.assertEqual(policy["max_parallel"]["DEEP"], 4)
        self.assertEqual(policy["provider_voting"], "forbidden")
        self.assertTrue(policy["quota"]["circumvention_forbidden"])

    def test_reference_sources_are_registered_without_authority(self):
        rows = self._yaml("AI_SKILL_LIBRARY/v4/model_mesh/upstreams.yaml")["sources"]
        by_id = {row["id"]: row for row in rows}
        expected = {
            "anomalyco/models.dev": "MIT",
            "anomalyco/opencode": "MIT",
            "Portkey-AI/models": "MIT",
            "Portkey-AI/gateway": "MIT",
            "vllm-project/semantic-router": "Apache-2.0",
            "microsoft/agent-framework": "MIT",
        }
        for source_id, license_id in expected.items():
            self.assertIn(source_id, by_id)
            self.assertEqual(by_id[source_id]["license"], license_id)
            self.assertFalse(by_id[source_id]["routing_authority"])
            self.assertFalse(by_id[source_id]["reasoning_authority"])
            self.assertFalse(by_id[source_id]["mandatory_runtime_dependency"])
            self.assertFalse(by_id[source_id]["code_reuse"])

    def test_capability_fusion_mirrors_model_mesh_references(self):
        fusion = self._yaml("AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        rows = fusion["upstream_pattern_map"]
        for source_id in (
            "anomalyco/models.dev",
            "anomalyco/opencode",
            "Portkey-AI/models",
            "Portkey-AI/gateway",
            "vllm-project/semantic-router",
            "microsoft/agent-framework",
        ):
            self.assertIn(source_id, rows)
            self.assertFalse(rows[source_id]["routing_authority"])
            self.assertFalse(rows[source_id]["reasoning_authority"])
            self.assertFalse(rows[source_id]["mandatory_runtime_dependency"])

    def test_model_mesh_is_warm_not_hot(self):
        workspace = self._yaml("AI_SKILL_LIBRARY/v4/index/workspace_map.yaml")
        self.assertIn("AI_SKILL_LIBRARY/v4/model_mesh", workspace["tiers"]["WARM"]["paths"])
        self.assertNotIn("AI_SKILL_LIBRARY/v4/model_mesh", workspace["tiers"]["HOT"]["paths"])
        self.assertIn("model_mesh", workspace["groups"])


if __name__ == "__main__":
    unittest.main()
