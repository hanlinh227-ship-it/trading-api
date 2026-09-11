import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"
V4 = LIB / "v4"


class V4ContractTests(unittest.TestCase):
    def test_required_v4_structure_exists(self):
        required = [
            "GITHUB_BRAIN_V4.md",
            "v4/stable/kernel.yaml",
            "v4/stable/router.yaml",
            "v4/stable/runtime.yaml",
            "v4/stable/security.yaml",
            "v4/stable/memory.yaml",
            "v4/stable/context.yaml",
            "v4/stable/evidence.yaml",
            "v4/stable/reliability.yaml",
            "v4/stable/observability.yaml",
            "v4/stable/reputation.yaml",
            "v4/evergreen/policy.yaml",
            "v4/evergreen/discovery.yaml",
            "v4/evergreen/promotion.yaml",
            "v4/evergreen/conflicts.yaml",
            "v4/mesh/graph.yaml",
            "v4/mesh/bridges.yaml",
            "v4/releases/current.json",
            "v4/releases/history.yaml",
            "v4/releases/4.0.0/manifest.yaml",
            "v4/tools/release.py",
            "v4/tools/mesh.py",
            "v4/tools/admission.py",
            "v4/tools/evaluate.py",
            "v4/tools/reputation.py",
            "v4/tools/evergreen.py",
            "validate_v4.py",
        ]
        for rel in required:
            self.assertTrue((LIB / rel).is_file(), rel)

    def test_checkpoint_promotes_v4_and_keeps_legacy_aliases(self):
        cp = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(cp["checkpoint_id"], "GITHUB_BRAIN_V4")
        self.assertEqual(cp["version"], "4.0.0")
        self.assertEqual(cp["checkpoint_path"], "AI_SKILL_LIBRARY/GITHUB_BRAIN_V4.md")
        self.assertEqual(cp["release_pointer_path"], "AI_SKILL_LIBRARY/v4/releases/current.json")
        self.assertTrue({"GITHUB_BRAIN_V3", "GITHUB_BRAIN_V2", "GITHUB_BRAIN_V1"}.issubset(cp["activation_aliases"]))

    def test_stable_and_evergreen_are_isolated(self):
        kernel = yaml.safe_load((V4 / "stable/kernel.yaml").read_text(encoding="utf-8"))
        self.assertIs(kernel["planes"]["stable"]["evergreen_required_for_requests"], False)
        self.assertIs(kernel["planes"]["evergreen"]["may_mutate_inflight_stable"], False)
        self.assertIs(kernel["invariants"]["stable_survives_evergreen_failure"], True)
        self.assertIs(kernel["invariants"]["new_skills_quarantine_before_routing"], True)

    def test_fast_path_remains_lightweight(self):
        runtime = yaml.safe_load((V4 / "stable/runtime.yaml").read_text(encoding="utf-8"))
        fast = runtime["profiles"]["FAST"]
        self.assertEqual(fast["durable_memory_items"], 0)
        self.assertEqual(fast["tool_candidates"], 0)
        self.assertEqual(fast["max_bridge_nodes"], 0)
        self.assertIs(fast["evergreen_sync"], False)
        self.assertIs(fast["preload_trading"], False)

    def test_mesh_is_namespaced_and_bounded(self):
        graph = yaml.safe_load((V4 / "mesh/graph.yaml").read_text(encoding="utf-8"))
        bridges = yaml.safe_load((V4 / "mesh/bridges.yaml").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(graph["domains"]), 10)
        ids = [d["id"] for d in graph["domains"]]
        self.assertEqual(len(ids), len(set(ids)))
        for bridge in bridges["bridges"]:
            self.assertIn(bridge["from"], ids)
            self.assertIn(bridge["to"], ids)
            self.assertLessEqual(bridge["max_context_tokens"], 2500)
        self.assertNotIn("trading", {b["to"] for b in bridges["bridges"] if b["from"] not in {"trading", "engineering"}})

    def test_evergreen_is_fail_closed(self):
        policy = yaml.safe_load((V4 / "evergreen/policy.yaml").read_text(encoding="utf-8"))
        self.assertIs(policy["quarantine_required"], True)
        self.assertIs(policy["stable_secret_access"], False)
        self.assertIs(policy["financial_execution"], False)
        self.assertIs(policy["permission_expansion_by_learning"], False)
        self.assertEqual(policy["default_promotion"], "deny")

    def test_trading_authority_is_unchanged(self):
        projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))
        trading = next(row for row in projects["projects"] if row["id"] == "trading")
        self.assertEqual(trading["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        self.assertEqual(trading["canonical_checkpoint"], "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md")


if __name__ == "__main__":
    unittest.main()
