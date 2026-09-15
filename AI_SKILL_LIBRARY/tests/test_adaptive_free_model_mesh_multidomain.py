import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.model_mesh import required_capabilities


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DOMAINS = {
    "core", "engineering", "trading", "game", "design_2d", "design_3d",
    "adobe", "prompt_media", "writing", "academic", "data_docs", "business",
}
EXPECTED_DIMENSIONS = {
    "text_reasoning", "coding", "math_quant", "long_context", "multilingual",
    "vision", "structured_output", "tool_calling", "planning", "creative_writing",
    "prompt_media", "research_synthesis", "data_analysis", "low_latency",
}


class AdaptiveFreeModelMeshMultidomainTests(unittest.TestCase):
    def _yaml(self, rel: str) -> dict:
        path = ROOT / rel
        self.assertTrue(path.is_file(), rel)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict, rel)
        return data

    def test_domain_capability_map_covers_every_canonical_domain(self):
        graph = self._yaml("AI_SKILL_LIBRARY/v4/mesh/graph.yaml")
        canonical = {row["id"] for row in graph["domains"]}
        self.assertEqual(canonical, EXPECTED_DOMAINS)

        mapping = self._yaml("AI_SKILL_LIBRARY/v4/model_mesh/domain_capabilities.yaml")
        self.assertEqual(set(mapping["dimensions"]), EXPECTED_DIMENSIONS)
        self.assertEqual(set(mapping["domains"]), EXPECTED_DOMAINS)
        self.assertTrue(mapping["domains"]["trading"]["research_only"])

    def test_required_capabilities_resolve_all_domains(self):
        for domain in sorted(EXPECTED_DOMAINS):
            requirements = required_capabilities(domain, "test_skill")
            self.assertTrue(requirements, domain)
            self.assertTrue(set(requirements).issubset(EXPECTED_DIMENSIONS), domain)
            for weight in requirements.values():
                self.assertGreaterEqual(weight, 0.0)
                self.assertLessEqual(weight, 1.0)

    def test_image_input_adds_strong_vision_requirement(self):
        no_image = required_capabilities("prompt_media", "video_prompt", has_image=False)
        with_image = required_capabilities("prompt_media", "video_prompt", has_image=True)
        self.assertGreaterEqual(with_image["vision"], 0.8)
        self.assertGreaterEqual(with_image["vision"], no_image.get("vision", 0.0))

    def test_unknown_domain_fails_closed(self):
        with self.assertRaises(ValueError):
            required_capabilities("not_a_domain", "anything")


if __name__ == "__main__":
    unittest.main()
