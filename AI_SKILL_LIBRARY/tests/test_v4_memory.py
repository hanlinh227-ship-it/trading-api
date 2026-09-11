import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "AI_SKILL_LIBRARY" / "v4"


class V4MemoryTests(unittest.TestCase):
    def test_memory_is_domain_scoped_and_authority_subordinate(self):
        data = yaml.safe_load((V4 / "stable/memory.yaml").read_text(encoding="utf-8"))
        self.assertIs(data["policy"]["domain_scoped"], True)
        self.assertIs(data["policy"]["current_authority_precedes_memory"], True)
        self.assertIs(data["policy"]["contradiction_requires_reverification"], True)
        self.assertIn("superseded_by", data["required_metadata"])
        self.assertIn("domain", data["required_metadata"])
        self.assertIs(data["maintenance"]["decay_enabled"], True)
        self.assertIs(data["maintenance"]["garbage_collect_redundant"], True)


if __name__ == "__main__":
    unittest.main()
