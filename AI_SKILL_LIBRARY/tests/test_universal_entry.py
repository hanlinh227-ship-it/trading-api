from __future__ import annotations

import unittest

from AI_SKILL_LIBRARY.v4.tools.universal_entry import (
    classify_entry,
    normalize_request,
    scope_allows,
)


class UniversalEntryTests(unittest.TestCase):
    def test_fast_text_stays_zero_rtt_eligible(self) -> None:
        req = normalize_request(
            {
                "text": "giải thích khái niệm API",
                "request_id": "r1",
                "session_id": "s1",
            },
            "chatgpt",
        )
        out = classify_entry(req)
        self.assertEqual(out["profile"], "FAST")
        self.assertFalse(out["requires_online_brain"])
        self.assertTrue(out["safe_degraded_allowed"])
        self.assertFalse(out["high_impact"])

    def test_live_trading_escalates_and_disallows_degraded(self) -> None:
        req = normalize_request(
            {
                "text": "quét giá BTC live và tìm entry",
                "request_id": "r2",
                "session_id": "s1",
                "freshness": "live",
            },
            "chatgpt",
        )
        out = classify_entry(req)
        self.assertEqual(out["profile"], "DEEP")
        self.assertTrue(out["requires_online_brain"])
        self.assertFalse(out["safe_degraded_allowed"])
        self.assertTrue(out["high_impact"])

    def test_deploy_escalates_to_deep(self) -> None:
        req = normalize_request(
            {
                "text": "deploy bản này lên production",
                "request_id": "r3",
                "session_id": "s1",
                "requested_action_class": "deployment_or_runtime_claim",
            },
            "claude",
        )
        out = classify_entry(req)
        self.assertEqual(out["profile"], "DEEP")
        self.assertFalse(out["safe_degraded_allowed"])

    def test_artifact_or_external_tool_defaults_standard(self) -> None:
        req = normalize_request(
            {
                "text": "tạo báo cáo từ project",
                "request_id": "r4",
                "session_id": "s1",
                "tool_classes": ["artifact_creation"],
            },
            "gemini",
        )
        out = classify_entry(req)
        self.assertEqual(out["profile"], "STANDARD")
        self.assertTrue(out["requires_online_brain"])
        self.assertTrue(out["safe_degraded_allowed"])

    def test_unknown_data_class_fails_closed_to_secret(self) -> None:
        req = normalize_request(
            {
                "text": "phân tích nội dung này",
                "request_id": "r5",
                "session_id": "s1",
                "data_class": "mystery",
            },
            "chatgpt",
        )
        self.assertEqual(req["data_class"], "SECRET")
        out = classify_entry(req)
        self.assertEqual(out["profile"], "DEEP")
        self.assertFalse(out["safe_degraded_allowed"])

    def test_normalization_never_accepts_empty_text(self) -> None:
        with self.assertRaises(ValueError):
            normalize_request({"text": "", "request_id": "r6", "session_id": "s1"}, "chatgpt")

    def test_normalization_rejects_unknown_adapter(self) -> None:
        with self.assertRaises(ValueError):
            normalize_request({"text": "hello", "request_id": "r7", "session_id": "s1"}, "unknown")

    def test_scopes_are_explicit_and_fail_closed(self) -> None:
        adapter = {"scopes": ["brain.route", "brain.read_context"]}
        self.assertTrue(scope_allows(adapter, "brain.route"))
        self.assertFalse(scope_allows(adapter, "brain.request_deploy_action"))
        self.assertFalse(scope_allows({}, "brain.route"))

    def test_client_capabilities_and_tools_are_bounded_strings(self) -> None:
        req = normalize_request(
            {
                "text": "test",
                "request_id": "r8",
                "session_id": "s1",
                "declared_capabilities": ["vision", "text"],
                "tool_classes": ["research"],
            },
            "chatgpt",
        )
        self.assertEqual(req["declared_capabilities"], ["vision", "text"])
        self.assertEqual(req["tool_classes"], ["research"])


if __name__ == "__main__":
    unittest.main()
