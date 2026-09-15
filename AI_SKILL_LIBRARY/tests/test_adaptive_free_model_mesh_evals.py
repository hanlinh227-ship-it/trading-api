from pathlib import Path
import unittest

import yaml

from AI_SKILL_LIBRARY.v4.tools.evaluate_model_mesh import evaluate_case, load_benchmarks


ROOT = Path(__file__).resolve().parents[2]


class AdaptiveFreeModelMeshEvalTests(unittest.TestCase):
    def test_benchmark_covers_all_canonical_domains(self):
        data = load_benchmarks(ROOT)
        expected = {
            "core", "engineering", "trading", "game", "design_2d", "design_3d",
            "adobe", "prompt_media", "writing", "academic", "data_docs", "business",
        }
        self.assertEqual(set(data["domains"]), expected)
        self.assertTrue(data["protected_dimensions"])
        for name in ["correctness", "authority", "security", "verification", "project_isolation", "no_secret_leakage", "FAST_latency_contract"]:
            self.assertIn(name, data["protected_dimensions"])

    def test_valid_public_contract_output_passes(self):
        case = {
            "id": "core-public",
            "domain": "core",
            "data_class": "PUBLIC",
            "requires_live_state": False,
            "required_fields": ["task_id", "input_hash", "model_family", "verification_status"],
        }
        output = {
            "task_id": "t1",
            "input_hash": "abc",
            "model_family": "family-a",
            "verification_status": "contract_checked",
            "claims": [{"claim_id": "c1", "value": "supported", "source_refs": ["ref:1"]}],
        }
        result = evaluate_case(case, output)
        self.assertTrue(result["passed"], result)

    def test_fake_live_trading_state_is_rejected(self):
        case = {
            "id": "trading-live",
            "domain": "trading",
            "data_class": "PUBLIC",
            "requires_live_state": True,
            "required_fields": ["task_id", "input_hash", "model_family", "verification_status"],
        }
        output = {
            "task_id": "t2",
            "input_hash": "abc",
            "model_family": "family-a",
            "verification_status": "model_claimed_live",
            "live_state": {"status": "LIVE", "source_refs": []},
        }
        result = evaluate_case(case, output)
        self.assertFalse(result["passed"])
        self.assertIn("live_state_unverified", result["failures"])

    def test_schema_and_privacy_mismatch_fail_closed(self):
        case = {
            "id": "internal-case",
            "domain": "data_docs",
            "data_class": "INTERNAL",
            "requires_live_state": False,
            "required_fields": ["task_id", "input_hash", "model_family", "verification_status"],
        }
        output = {"task_id": "t3", "privacy_class": "public_safe"}
        result = evaluate_case(case, output)
        self.assertFalse(result["passed"])
        self.assertIn("schema_invalid", result["failures"])
        self.assertIn("privacy_mismatch", result["failures"])


if __name__ == "__main__":
    unittest.main()
