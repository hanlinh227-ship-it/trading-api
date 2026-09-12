from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


class SkillMandatoryPolicyTests(unittest.TestCase):
    def test_every_profile_requires_exactly_one_primary_skill(self):
        router = load("AI_SKILL_LIBRARY/v4/stable/router.yaml")
        runtime = load("AI_SKILL_LIBRARY/v4/stable/runtime.yaml")
        self.assertIs(router["policy"]["primary_skill_required"], True)
        self.assertEqual(router["policy"]["fallback_primary_skill"], "core_reasoning")
        self.assertIs(router["policy"]["skill_execution_capsule_required"], True)
        for name in ("FAST", "STANDARD", "DEEP"):
            self.assertEqual(runtime["profiles"][name]["primary_skill_count"], 1)
            self.assertIs(runtime["profiles"][name]["skill_capsule_required"], True)
        self.assertEqual(runtime["profiles"]["FAST"]["max_supporting_skills"], 0)


if __name__ == "__main__":
    unittest.main()
