from copy import deepcopy
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXED_SHA = "a" * 40


class SkillGatewayCompilerTests(unittest.TestCase):
    def _module(self):
        from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot, validate_aliases
        return compile_snapshot, validate_aliases

    def test_snapshot_is_deterministic_except_generated_at(self):
        compile_snapshot, _ = self._module()
        left = compile_snapshot(ROOT, FIXED_SHA, generated_at="2026-09-12T00:00:00Z")
        right = compile_snapshot(ROOT, FIXED_SHA, generated_at="2026-09-12T00:00:01Z")
        self.assertNotEqual(left["generated_at"], right["generated_at"])
        left = deepcopy(left)
        right = deepcopy(right)
        left.pop("generated_at", None)
        right.pop("generated_at", None)
        self.assertEqual(left, right)

    def test_snapshot_contains_core_reasoning_capsule(self):
        compile_snapshot, _ = self._module()
        snapshot = compile_snapshot(ROOT, FIXED_SHA, generated_at="2026-09-12T00:00:00Z")
        self.assertEqual(snapshot["fallback_primary_skill"], "core_reasoning")
        capsule = snapshot["capsules"]["core_reasoning"]
        self.assertEqual(capsule["skill_id"], "core_reasoning")
        self.assertTrue(capsule["output_contract"])
        self.assertTrue(capsule["capsule_hash"])

    def test_vietnamese_aliases_route_to_canonical_skill_ids_only(self):
        compile_snapshot, _ = self._module()
        snapshot = compile_snapshot(ROOT, FIXED_SHA, generated_at="2026-09-12T00:00:00Z")
        aliases = snapshot["aliases"]
        self.assertIn("sửa lỗi", aliases["debugging"])
        self.assertIn("viết quảng cáo", aliases["advertising_copy"])
        self.assertIn("quét market", aliases["trading_router"])
        for skill_id in aliases:
            self.assertIn(skill_id, snapshot["skills"])

    def test_snapshot_rejects_unknown_alias_skill(self):
        _, validate_aliases = self._module()
        with self.assertRaises(ValueError):
            validate_aliases({"aliases": {"not_a_skill": ["x"]}}, {"core_reasoning"})

    def test_snapshot_contains_no_secret_shaped_fields(self):
        compile_snapshot, _ = self._module()
        snapshot = compile_snapshot(ROOT, FIXED_SHA, generated_at="2026-09-12T00:00:00Z")
        banned = re.compile(r"secret|token|password|private_key|api_key|credential", re.I)

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIsNone(banned.search(str(key)), f"sensitive key in snapshot: {key}")
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(snapshot)


if __name__ == "__main__":
    unittest.main()
