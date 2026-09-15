import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


class AdaptiveFreeModelMeshEvergreenTests(unittest.TestCase):
    def test_continuous_intelligence_declares_hourly_evergreen_mesh_discovery(self):
        data = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/stable/continuous_intelligence.yaml").read_text(encoding="utf-8"))
        mesh = data["model_mesh_discovery"]
        self.assertEqual(mesh["plane"], "evergreen_only")
        self.assertEqual(mesh["cadence"], "hourly")
        self.assertFalse(mesh["stable_request_dependency"])
        self.assertEqual(mesh["output_state"], "quarantine")
        self.assertTrue(mesh["free_status_revalidation"])
        self.assertTrue(mesh["privacy_terms_revalidation"])
        self.assertTrue(mesh["model_family_dedupe"])
        self.assertFalse(mesh["auto_permission_expansion"])

    def test_evergreen_discovery_policy_matches_stable_contract(self):
        data = yaml.safe_load((ROOT / "AI_SKILL_LIBRARY/v4/evergreen/discovery.yaml").read_text(encoding="utf-8"))
        mesh = data["model_mesh_discovery"]
        self.assertEqual(mesh["plane"], "evergreen_only")
        self.assertEqual(mesh["cadence"], "hourly")
        self.assertFalse(mesh["stable_request_dependency"])
        self.assertEqual(mesh["output_state"], "quarantine")
        self.assertFalse(mesh["auto_permission_expansion"])

    def test_hourly_workflow_discovers_models_and_uploads_quarantine_report(self):
        text = (ROOT / ".github/workflows/ai-brain-evergreen-scan.yml").read_text(encoding="utf-8")
        self.assertIn("discover_free_models.py --root . --output /tmp/v4-free-model-mesh-candidates.json", text)
        self.assertIn("/tmp/v4-free-model-mesh-candidates.json", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("git push", text)


if __name__ == "__main__":
    unittest.main()
