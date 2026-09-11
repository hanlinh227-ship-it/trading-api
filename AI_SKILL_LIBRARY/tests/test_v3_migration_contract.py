import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


class BrainV3MigrationContractTests(unittest.TestCase):
    def test_required_v22_to_v3_files_exist(self):
        for rel in (
            "context.yaml",
            "reliability.yaml",
            "evidence.yaml",
            "orchestration.yaml",
            "kernel.yaml",
            "migration.yaml",
            "GITHUB_BRAIN_V3.md",
            "validate_v3.py",
            "schemas/kernel.schema.json",
        ):
            self.assertTrue((LIB / rel).is_file(), rel)

    def test_migration_registry_records_all_requested_milestones(self):
        data = yaml.safe_load((LIB / "migration.yaml").read_text(encoding="utf-8"))
        versions = [row["version"] for row in data["milestones"]]
        self.assertEqual(versions, ["2.1.0", "2.2.0", "2.3.0", "2.4.0", "3.0.0"])
        self.assertEqual(data["current"], "3.0.0")
        self.assertEqual(data["authority"], "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md")

    def test_checkpoint_promotes_v3_and_keeps_v1_v2_compatibility(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["checkpoint_id"], "GITHUB_BRAIN_V3")
        self.assertEqual(checkpoint["version"], "3.0.0")
        self.assertEqual(checkpoint["checkpoint_path"], "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md")
        self.assertEqual(checkpoint["kernel_path"], "AI_SKILL_LIBRARY/kernel.yaml")
        self.assertIn("GITHUB_BRAIN_V2", checkpoint["activation_aliases"])
        self.assertIn("GITHUB_BRAIN_V1", checkpoint["activation_aliases"])

    def test_v2_becomes_redirect_only_and_v3_is_single_ai_brain_authority(self):
        v2 = (LIB / "GITHUB_BRAIN_V2.md").read_text(encoding="utf-8")
        self.assertIn("GITHUB_BRAIN_V3", v2)
        self.assertIn("compatibility", v2.lower())
        self.assertNotIn("CURRENT_AUTHORITY", v2)

        projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))
        ai = [row for row in projects["projects"] if row["id"] == "ai_brain"]
        self.assertEqual(len(ai), 1)
        self.assertEqual(ai[0]["authority"], "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md")

        router = yaml.safe_load((LIB / "router.yaml").read_text(encoding="utf-8"))
        current = [row for row in router["authorities"] if row["scope"] == "ai_brain" and row["status"] == "CURRENT_AUTHORITY"]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["path"], "AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md")

    def test_v22_context_scheduler_is_bounded_and_fast_safe(self):
        data = yaml.safe_load((LIB / "context.yaml").read_text(encoding="utf-8"))
        self.assertIs(data["policy"]["authority_first"], True)
        self.assertIs(data["policy"]["deduplicate"], True)
        self.assertIs(data["policy"]["cache_never_outranks_fresh_authority"], True)
        self.assertEqual(data["profiles"]["FAST"]["max_registry_reads"], 1)
        self.assertEqual(data["profiles"]["FAST"]["durable_memory_items"], 0)
        self.assertIn("checkpoint_change", data["cache"]["invalidate_on"])

    def test_v23_reliability_and_evidence_are_bounded(self):
        reliability = yaml.safe_load((LIB / "reliability.yaml").read_text(encoding="utf-8"))
        evidence = yaml.safe_load((LIB / "evidence.yaml").read_text(encoding="utf-8"))
        self.assertLessEqual(reliability["retry"]["max_attempts"], 3)
        self.assertIs(reliability["circuit_breaker"]["enabled"], True)
        self.assertIs(reliability["fallback"]["must_disclose_degraded_state"], True)
        self.assertIs(evidence["ledger"]["persist_hidden_reasoning"], False)
        self.assertIs(evidence["conflicts"]["prefer_current_authority"], True)
        self.assertIs(evidence["uncertainty"]["escalate_material_conflict"], True)

    def test_v24_orchestration_parallelism_is_bounded_and_safe(self):
        data = yaml.safe_load((LIB / "orchestration.yaml").read_text(encoding="utf-8"))
        self.assertIs(data["task_graph"]["enabled"], True)
        self.assertLessEqual(data["parallelism"]["max_parallel_tasks"], 4)
        self.assertIs(data["parallelism"]["dependency_aware"], True)
        self.assertIs(data["parallelism"]["serial_fallback"], True)
        self.assertIs(data["safety"]["parallel_high_impact_writes"], False)

    def test_v3_kernel_unifies_control_plane_and_keeps_fast_path_light(self):
        kernel = yaml.safe_load((LIB / "kernel.yaml").read_text(encoding="utf-8"))
        self.assertEqual(kernel["version"], 3)
        self.assertEqual(kernel["authority"], "GITHUB_BRAIN_V3")
        self.assertEqual(kernel["default_profile"], "FAST")
        self.assertEqual(kernel["profiles"]["FAST"]["orchestration"], "serial")
        self.assertEqual(kernel["profiles"]["FAST"]["durable_memory_items"], 0)
        self.assertIs(kernel["invariants"]["one_ai_brain_authority"], True)
        self.assertIs(kernel["invariants"]["no_hidden_reasoning_persistence"], True)
        self.assertIs(kernel["invariants"]["no_auto_merge_self_improvement"], True)

    def test_trading_authority_is_unchanged(self):
        projects = yaml.safe_load((LIB / "projects.yaml").read_text(encoding="utf-8"))
        trading = next(row for row in projects["projects"] if row["id"] == "trading")
        self.assertEqual(trading["authority"], "docs/checkpoints/CURRENT_HANDOFF.md")
        self.assertEqual(trading["canonical_checkpoint"], "docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md")


if __name__ == "__main__":
    unittest.main()
