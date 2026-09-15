import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class PeerTriLayerPolicyTests(unittest.TestCase):
    def test_layers_are_peers_but_not_authorities(self):
        policy = load_yaml(ROOT / "AI_SKILL_LIBRARY/v4/learning/policy.yaml")
        self.assertEqual(policy["peer_layers"], ["experience", "curated", "exploration"])
        self.assertFalse(policy["routing_authority"])
        self.assertFalse(policy["reasoning_authority"])
        self.assertEqual(policy["fixed_layer_priority"], "forbidden")
        self.assertEqual(policy["majority_vote_for_truth"], "forbidden")
        self.assertEqual(policy["permission_expansion_by_learning"], "forbidden")
        self.assertTrue(policy["risk_taxonomy_is_separate"])
        self.assertEqual(policy["stable_direct_write"], "forbidden")

    def test_legion_keeps_existing_concurrency_ceiling(self):
        policy = load_yaml(ROOT / "AI_SKILL_LIBRARY/v4/legion/policy.yaml")
        self.assertEqual(policy["max_parallel"], {"FAST": 0, "STANDARD": 2, "DEEP": 4})
        self.assertTrue(policy["single_commander"])
        self.assertEqual(policy["commander"], "GITHUB_BRAIN_V4")
        self.assertFalse(policy["routing_authority"])
        self.assertFalse(policy["reasoning_authority"])
        self.assertFalse(policy["fast_path_preload"])

    def test_sources_define_three_peer_planes_without_priority(self):
        sources = load_yaml(ROOT / "AI_SKILL_LIBRARY/v4/learning/sources.yaml")
        self.assertEqual(set(sources["layers"]), {"experience", "curated", "exploration"})
        for layer in sources["layers"].values():
            self.assertEqual(layer["epistemic_priority"], "peer")
            self.assertFalse(layer["routing_authority"])
            self.assertFalse(layer["reasoning_authority"])

    def test_upstreams_are_reference_only(self):
        fusion = load_yaml(ROOT / "AI_SKILL_LIBRARY/v4/stable/capability_fusion.yaml")
        upstreams = fusion["upstream_pattern_map"]
        required = {
            "Shubhamsaboo/awesome-llm-apps": "Apache-2.0",
            "anomalyco/opencode": "MIT",
            "ECNU-ICALK/AutoSkill": "MIT",
            "ECNU-ICALK/AutoSkill/SkillEvo": "MIT",
        }
        for key, license_name in required.items():
            self.assertIn(key, upstreams)
            entry = upstreams[key]
            self.assertEqual(entry.get("license"), license_name)
            self.assertFalse(entry.get("routing_authority", True))
            self.assertFalse(entry.get("reasoning_authority", True))
            self.assertFalse(entry.get("mandatory_runtime_dependency", True))
            self.assertFalse(entry.get("code_reuse", True))

    def test_legion_and_learning_are_warm_not_hot(self):
        workspace = load_yaml(ROOT / "AI_SKILL_LIBRARY/v4/index/workspace_map.yaml")
        warm = workspace["tiers"]["WARM"]["paths"]
        hot = workspace["tiers"]["HOT"]["paths"]
        for path in ("AI_SKILL_LIBRARY/v4/legion", "AI_SKILL_LIBRARY/v4/learning"):
            self.assertIn(path, warm)
            self.assertNotIn(path, hot)


if __name__ == "__main__":
    unittest.main()
