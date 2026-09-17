import unittest

from AI_SKILL_LIBRARY.v4.control_plane.ingress import prepare_ingress
from AI_SKILL_LIBRARY.v4.control_plane.verifier import verify_output


class IngressTests(unittest.TestCase):
    def envelope(self):
        return {
            "request_id": "req-1", "source": "chatgpt", "request": "fix code",
            "project_context": {}, "conversation_context": {}, "attachments": [],
            "constraints": {"FREE_ONLY": True, "permissions": ["read", "branch_write"]},
            "privacy_class": "CONFIDENTIAL", "desired_depth": "STANDARD",
        }

    def route(self):
        return {"routed_by": "task_router", "domain": "CODING", "primary_skill": "coding", "profile": "STANDARD"}

    def test_missing_required_input_fails_closed(self):
        row = self.envelope(); del row["request_id"]
        with self.assertRaisesRegex(ValueError, "request_id"):
            prepare_ingress(row, self.route())

    def test_router_is_mandatory_and_ingress_does_not_select_model(self):
        with self.assertRaisesRegex(ValueError, "task_router"):
            prepare_ingress(self.envelope(), {**self.route(), "routed_by": "other"})
        result = prepare_ingress(self.envelope(), self.route())
        self.assertNotIn("model_id", result)
        self.assertNotIn("primary_model", result)
        self.assertEqual(result["selection_request"]["privacy"], "CONFIDENTIAL")
        self.assertTrue(result["policy_ceiling"]["FREE_ONLY"])
        self.assertEqual(result["policy_ceiling"]["permissions"], ["read", "branch_write"])


class VerifierTests(unittest.TestCase):
    def test_coding_requires_real_tool_evidence(self):
        report = verify_output("CODING", {"answer": "done", "checks": {"tests": "pass", "compile": "pass", "static_analysis": "pass"}})
        self.assertFalse(report["passed"])
        self.assertIn("missing_check_evidence", report["failures"])
        passed = verify_output("CODING", {"answer": "done", "checks": {"tests": "pass", "compile": "pass", "static_analysis": "pass"}, "evidence_refs": ["run:1"]})
        self.assertTrue(passed["passed"])

    def test_math_structured_research_and_vietnamese(self):
        self.assertTrue(verify_output("MATH", {"answer": 4, "expected": 4, "tolerance": 0})["passed"])
        self.assertFalse(verify_output("STRUCTURED_OUTPUT", {"data": {"a": 1}, "required_fields": ["a", "b"]})["passed"])
        self.assertFalse(verify_output("RESEARCH", {"claims": [{"claim": "x", "source_refs": [], "freshness": None}]})["passed"])
        self.assertTrue(verify_output("VIETNAMESE", {"answer": "Đây là câu trả lời tiếng Việt.", "instruction_checks": [True], "factual_checks": [True]})["passed"])

    def test_trading_research_and_creative_constraints(self):
        stale = verify_output("TRADING_RESEARCH", {"data_fresh": False, "risk_evidence": [], "source_refs": []})
        self.assertFalse(stale["passed"])
        creative = verify_output("CREATIVE", {"constraints": {"no_camera_look": True, "fixed_camera": False}})
        self.assertFalse(creative["passed"])

    def test_unknown_verifier_fails_closed_and_no_majority_truth(self):
        report = verify_output("OTHER", {"votes": ["yes", "yes", "no"]})
        self.assertFalse(report["passed"])
        self.assertIn("unsupported_verifier", report["failures"])


if __name__ == "__main__":
    unittest.main()
