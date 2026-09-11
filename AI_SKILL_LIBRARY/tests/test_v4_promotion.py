import json
import tempfile
import unittest
from pathlib import Path

import yaml

from AI_SKILL_LIBRARY.v4.tools.evergreen import lifecycle_decision
from AI_SKILL_LIBRARY.v4.tools.release import rollback_release


class V4PromotionTests(unittest.TestCase):
    def test_class_a_can_auto_promote_only_when_all_gates_pass(self):
        result = lifecycle_decision(
            promotion_class="A",
            gates={"provenance": True, "license": True, "security": True, "authority": True, "evals": True, "canary": True},
            protected_regressions=[],
        )
        self.assertEqual(result, "promote")

    def test_missing_gate_blocks_promotion(self):
        result = lifecycle_decision(
            promotion_class="A",
            gates={"provenance": True, "license": True, "security": False, "authority": True, "evals": True, "canary": True},
            protected_regressions=[],
        )
        self.assertEqual(result, "reject")

    def test_class_d_never_auto_promotes(self):
        result = lifecycle_decision(
            promotion_class="D",
            gates={"provenance": True, "license": True, "security": True, "authority": True, "evals": True, "canary": True},
            protected_regressions=[],
        )
        self.assertEqual(result, "manual_authorization_required")

    def test_rollback_restores_previous_known_good(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases = root / "AI_SKILL_LIBRARY/v4/releases"
            (releases / "4.0.0").mkdir(parents=True)
            (releases / "4.0.1").mkdir(parents=True)
            (releases / "current.json").write_text(json.dumps({"version": "4.0.1", "manifest_path": "AI_SKILL_LIBRARY/v4/releases/4.0.1/manifest.yaml", "manifest_sha256": "x"}), encoding="utf-8")
            (releases / "history.yaml").write_text(yaml.safe_dump({"releases": [{"version": "4.0.0", "known_good": True}, {"version": "4.0.1", "known_good": True}]}), encoding="utf-8")
            (releases / "4.0.0/manifest.yaml").write_text("version: 4.0.0\n", encoding="utf-8")
            version = rollback_release(root)
            self.assertEqual(version, "4.0.0")
            current = json.loads((releases / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(current["version"], "4.0.0")


if __name__ == "__main__":
    unittest.main()
