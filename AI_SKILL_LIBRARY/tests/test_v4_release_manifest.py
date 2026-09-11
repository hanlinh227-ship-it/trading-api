import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "AI_SKILL_LIBRARY/v4/releases/4.0.0/manifest.yaml"


class V4ReleaseManifestTests(unittest.TestCase):
    def test_manifest_contains_core_v4_roles(self):
        data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["architecture"], "GITHUB_BRAIN_V4")
        roles = {row["role"] for row in data["files"]}
        self.assertTrue({"kernel", "runtime", "router", "mesh", "evergreen", "security"}.issubset(roles))
        self.assertIs(data["promotion"]["validated"], True)


if __name__ == "__main__":
    unittest.main()
