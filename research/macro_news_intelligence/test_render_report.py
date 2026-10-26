"""Offline deterministic Markdown synthesis contract."""
import unittest
from datetime import datetime, timezone

import news_skill
import render_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.sample = news_skill.classify([
            {"title": "Gold XAUUSD jumps after Fed rate decision",
             "published": "2026-10-26T03:00:00Z", "source": "official",
             "url": "https://example.org/gold"},
            {"title": "OPEC discusses crude oil inventories",
             "published": "2026-10-26T02:00:00Z", "source": "official",
             "url": "https://example.org/oil"},
        ], datetime(2026, 10, 26, 4, tzinfo=timezone.utc))

    def test_each_market_and_sources(self):
        body = render_report.create_brief(self.sample)
        self.assertIn("XAUUSD", body)
        self.assertIn("Dầu WTI", body)
        self.assertIn("Dầu Brent", body)
        self.assertIn("https://example.org/oil", body)
        self.assertIn("NEWS_UNVERIFIED", body)

    def test_filter_specific_market(self):
        body = render_report.create_brief(self.sample, market="WTI")
        self.assertIn("Dầu WTI", body)
        self.assertNotIn("## Vàng", body)

    def test_rejects_execution_authorized_and_fake_news_clear(self):
        for key, value in (("executionAuthorized", True), ("hardNewsClearance", "NEWS_CLEAR")):
            payload = {**self.sample, key: value}
            with self.assertRaises(ValueError):
                render_report.create_brief(payload)

    def test_safe_markdown_and_untrusted_urls(self):
        self.sample["articles"].append({
            "title": "<script>alert(1)</script>", "url": "javascript:alert(1)",
            "markets": ["WTI"], "topics": ["GEO_RISK"], "sources": ["untrusted"],
            "freshness": "UNKNOWN",
        })
        brief = render_report.create_brief(self.sample, market="WTI")
        self.assertNotIn("<script>", brief)
        self.assertNotIn("javascript:", brief)
        self.assertIn("&lt;script&gt;", brief)

    def test_offline_calendar_provenance(self):
        self.sample["calendar"] = {
            "sourceVerified": False, "events": [{
                "title": "Employment Situation",
                "scheduledAt": "2026-11-06T13:30:00Z",
                "markets": ["FOREX", "XAUUSD"], "inEventWindow": True,
            }]
        }
        brief = render_report.create_brief(self.sample, market="FOREX")
        self.assertIn("CHƯA XÁC MINH", brief)
        self.assertIn("GẦN GIỜ CÔNG BỐ", brief)


if __name__ == "__main__":
    unittest.main()
