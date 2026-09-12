import copy
import unittest
from pathlib import Path

from AI_SKILL_LIBRARY.v4.tools.compile_skill_gateway import compile_snapshot
from AI_SKILL_LIBRARY.v4.tools.validate_skill_gateway_snapshot import validate_snapshot

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40


class SkillGatewayCompilerTests(unittest.TestCase):
    def test_snapshot_is_deterministic_for_fixed_timestamp(self):
        one = compile_snapshot(ROOT, SHA, generated_at="2026-09-12T00:00:00Z")
        two = compile_snapshot(ROOT, SHA, generated_at="2026-09-12T00:00:00Z")
        self.assertEqual(one, two)

    def test_snapshot_contains_core_reasoning_capsule(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-12T00:00:00Z")
        self.assertEqual(snapshot["fallback_primary_skill"], "core_reasoning")
        capsule = snapshot["capsules"]["core_reasoning"]
        self.assertEqual(capsule["skill_id"], "core_reasoning")
        self.assertTrue(capsule["output_contract"])
        self.assertIn("capsule_hash", capsule)

    def test_vietnamese_aliases_reference_canonical_skill_ids(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-12T00:00:00Z")
        self.assertIn("sửa lỗi", snapshot["skills"]["debugging"]["aliases"])
        self.assertIn("viết quảng cáo", snapshot["skills"]["advertising_copy"]["aliases"])
        self.assertIn("quét market", snapshot["skills"]["trading_router"]["aliases"])
        self.assertEqual(validate_snapshot(snapshot, ROOT), [])

    def test_validator_rejects_unknown_alias_skill(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-12T00:00:00Z")
        broken = copy.deepcopy(snapshot)
        broken["routing_aliases"]["not_a_real_skill"] = ["x"]
        errors = validate_snapshot(broken, ROOT)
        self.assertTrue(any("unknown alias skill" in error for error in errors))

    def test_validator_rejects_secret_shaped_fields(self):
        snapshot = compile_snapshot(ROOT, SHA, generated_at="2026-09-12T00:00:00Z")
        broken = copy.deepcopy(snapshot)
        broken["api_token"] = "forbidden"
        errors = validate_snapshot(broken, ROOT)
        self.assertTrue(any("sensitive key" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
