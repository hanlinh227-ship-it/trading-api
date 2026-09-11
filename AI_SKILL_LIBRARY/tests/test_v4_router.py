import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "AI_SKILL_LIBRARY" / "v4"


class V4RouterTests(unittest.TestCase):
    def test_router_uses_mesh_and_release_contract(self):
        data = yaml.safe_load((V4 / "stable/router.yaml").read_text(encoding="utf-8"))
        self.assertIs(data["policy"]["route_every_request"], True)
        self.assertEqual(data["policy"]["mandatory_router"], "task_router")
        self.assertIs(data["policy"]["knowledge_mesh_required"], True)
        self.assertIs(data["policy"]["release_bundle_only"], True)
        self.assertLessEqual(data["policy"]["max_supporting_skills"], 2)
        self.assertIs(data["policy"]["adaptive_profile_selection"], True)


if __name__ == "__main__":
    unittest.main()
