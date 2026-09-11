import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "AI_SKILL_LIBRARY"


class AgentRuntimeContractTests(unittest.TestCase):
    def test_runtime_files_exist(self):
        required = (
            "bootstrap.yaml", "runtime.yaml", "memory.yaml", "evals.yaml", "observability.yaml",
            "security.yaml", "context.yaml", "reliability.yaml", "evidence.yaml", "orchestration.yaml",
            "kernel.yaml", "schemas/runtime.schema.json", "schemas/kernel.schema.json", "validate_runtime.py", "validate_v3.py",
        )
        for rel in required:
            self.assertTrue((LIB / rel).is_file(), rel)

    def test_checkpoint_points_to_runtime_control_plane(self):
        checkpoint = json.loads((LIB / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["checkpoint_id"], "GITHUB_BRAIN_V3")
        self.assertEqual(checkpoint["version"], "3.0.0")
        expected = {
            "bootstrap_path": "AI_SKILL_LIBRARY/bootstrap.yaml",
            "kernel_path": "AI_SKILL_LIBRARY/kernel.yaml",
            "runtime_path": "AI_SKILL_LIBRARY/runtime.yaml",
            "context_path": "AI_SKILL_LIBRARY/context.yaml",
            "reliability_path": "AI_SKILL_LIBRARY/reliability.yaml",
            "evidence_path": "AI_SKILL_LIBRARY/evidence.yaml",
            "orchestration_path": "AI_SKILL_LIBRARY/orchestration.yaml",
            "memory_path": "AI_SKILL_LIBRARY/memory.yaml",
            "evals_path": "AI_SKILL_LIBRARY/evals.yaml",
            "observability_path": "AI_SKILL_LIBRARY/observability.yaml",
            "security_path": "AI_SKILL_LIBRARY/security.yaml",
            "runtime_validator_path": "AI_SKILL_LIBRARY/validate_runtime.py",
            "v3_validator_path": "AI_SKILL_LIBRARY/validate_v3.py",
        }
        for key, value in expected.items():
            self.assertEqual(checkpoint[key], value)
        self.assertIn("GITHUB_BRAIN_V2", checkpoint["activation_aliases"])
        self.assertIn("GITHUB_BRAIN_V1", checkpoint["activation_aliases"])

    def test_bootstrap_is_compact_and_future_discoverable(self):
        bootstrap = yaml.safe_load((LIB / "bootstrap.yaml").read_text(encoding="utf-8"))
        self.assertEqual(bootstrap["checkpoint_id"], "GITHUB_BRAIN_V3")
        self.assertEqual(bootstrap["protocol_version"], "3.0.0")
        self.assertEqual(bootstrap["mandatory_router"], "task_router")
        self.assertEqual(bootstrap["default_profile"], "FAST")
        self.assertEqual(bootstrap["kernel"], "AI_SKILL_LIBRARY/kernel.yaml")
        self.assertIs(bootstrap["lazy_load"]["full_skill_catalog"], True)
        self.assertIs(bootstrap["lazy_load"]["project_state"], True)
        self.assertIs(bootstrap["lazy_load"]["trading_state"], True)
        self.assertLessEqual(len((LIB / "bootstrap.yaml").read_text(encoding="utf-8")), 7000)

    def test_runtime_has_fast_standard_deep_profiles_with_bounded_budgets(self):
        runtime = yaml.safe_load((LIB / "runtime.yaml").read_text(encoding="utf-8"))
        self.assertEqual(runtime["profile_order"], ["FAST", "STANDARD", "DEEP"])
        profiles = runtime["profiles"]
        self.assertEqual(set(profiles), {"FAST", "STANDARD", "DEEP"})
        fast = profiles["FAST"]
        self.assertEqual(fast["replan_budget"], 0)
        self.assertEqual(fast["max_supporting_skills"], 0)
        self.assertEqual(fast["memory_items"], 0)
        self.assertEqual(fast["tool_candidates"], 0)
        self.assertEqual(fast["orchestration"], "serial")
        self.assertNotIn("planner", fast["stages"])
        self.assertNotIn("critic", fast["stages"])
        self.assertNotIn("eval", fast["stages"])
        for name in ("FAST", "STANDARD", "DEEP"):
            row = profiles[name]
            for field in ("context_tokens", "memory_items", "tool_candidates", "replan_budget"):
                self.assertIsInstance(row[field], int, (name, field))
                self.assertGreaterEqual(row[field], 0, (name, field))
                self.assertLess(row[field], 100000, (name, field))
        self.assertLessEqual(profiles["FAST"]["context_tokens"], profiles["STANDARD"]["context_tokens"])
        self.assertLessEqual(profiles["STANDARD"]["context_tokens"], profiles["DEEP"]["context_tokens"])

    def test_runtime_schema_accepts_bounded_v22_v24_profile_fields(self):
        runtime = yaml.safe_load((LIB / "runtime.yaml").read_text(encoding="utf-8"))
        schema = json.loads((LIB / "schemas/runtime.schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(runtime))
        self.assertEqual(errors, [], [err.message for err in errors])
        profile_schema = schema["$defs"]["profile"]["properties"]
        self.assertEqual(profile_schema["context_registry_reads"]["maximum"], 10)
        self.assertEqual(profile_schema["max_parallel_tasks"]["maximum"], 4)
        self.assertIn("serial", profile_schema["orchestration"]["enum"])
        self.assertIn("dependency_graph", profile_schema["orchestration"]["enum"])

    def test_memory_policy_is_layered_bounded_and_private_by_default(self):
        memory = yaml.safe_load((LIB / "memory.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(memory["layers"]), {"working", "episodic", "semantic", "procedural"})
        exclusions = set(memory["privacy"]["durable_exclusions"])
        self.assertTrue({"secrets", "credentials", "private_keys", "account_data", "sensitive_personal_data", "raw_private_chat"}.issubset(exclusions))
        self.assertIs(memory["policy"]["retrieve_before_write"], True)
        self.assertIs(memory["policy"]["prefer_verified_current_over_old"], True)

    def test_eval_policy_turns_verified_failures_into_regression_candidates(self):
        evals = yaml.safe_load((LIB / "evals.yaml").read_text(encoding="utf-8"))
        self.assertIs(evals["learning_loop"]["verified_failure_to_candidate_eval"], True)
        gates = set(evals["promotion"]["required_gates"])
        self.assertTrue({"tests", "eval_baseline", "security", "authority", "ci"}.issubset(gates))
        self.assertIs(evals["promotion"]["automatic_merge"], False)

    def test_observability_never_persists_hidden_reasoning(self):
        obs = yaml.safe_load((LIB / "observability.yaml").read_text(encoding="utf-8"))
        self.assertIs(obs["policy"]["persist_hidden_chain_of_thought"], False)
        self.assertIn("decision_summary", obs["allowed_events"])
        self.assertNotIn("chain_of_thought", obs["allowed_events"])
        self.assertEqual(obs["profiles"]["FAST"]["persistence"], "none")

    def test_security_has_conservative_high_impact_defaults(self):
        security = yaml.safe_load((LIB / "security.yaml").read_text(encoding="utf-8"))
        classes = security["risk_classes"]
        self.assertEqual(classes["read_only"]["default"], "allow")
        self.assertNotEqual(classes["destructive"]["default"], "allow")
        self.assertNotEqual(classes["financial"]["default"], "allow")
        self.assertNotEqual(classes["credential_sensitive"]["default"], "allow")

    def test_router_declares_runtime_profile_selection_before_project_authority(self):
        router = yaml.safe_load((LIB / "router.yaml").read_text(encoding="utf-8"))
        order = router["execution_order"]
        self.assertIn("runtime_profile", order)
        self.assertLess(order.index("runtime_profile"), order.index("project_authority"))
        self.assertIs(router["defaults"]["adaptive_runtime"], True)
        self.assertEqual(router["defaults"]["default_runtime_profile"], "FAST")
        self.assertEqual(router["defaults"]["kernel_config_path"], "AI_SKILL_LIBRARY/kernel.yaml")


if __name__ == "__main__":
    unittest.main()
