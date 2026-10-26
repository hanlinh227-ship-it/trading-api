"""Offline contract tests for the non-trading macro-news classifier."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

SCRIPT = Path(__file__).with_name("news_skill.py")
spec = importlib.util.spec_from_file_location("news_skill", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW = datetime(2026, 10, 26, 4, 0, tzinfo=timezone.utc)


class MacroNewsResearchTests(unittest.TestCase):
    def test_cpi_impacts_fx_and_gold_without_direction_or_clearance(self):
        data = mod.classify([{
            "title": "US CPI inflation rises before Fed meeting",
            "source": "official-feed", "published": "2026-10-26T03:00:00Z",
            "url": "https://example.org/story",
        }], NOW)
        article = data["articles"][0]
        self.assertEqual(article["topics"], ["RATE_POLICY", "INFLATION"])
        self.assertEqual(article["markets"], ["FOREX", "XAUUSD"])
        self.assertEqual(article["freshness"], "FRESH")
        self.assertEqual(article["potentialImpact"], "HIGH_POTENTIAL")
        self.assertEqual(article["direction"], "UNKNOWN")
        self.assertFalse(data["economicCalendarVerified"])
        self.assertFalse(data["executionAuthorized"])
        self.assertEqual(data["hardNewsClearance"], "NEWS_UNVERIFIED")

    def test_opec_wti_brent(self):
        data = mod.classify([{"title": "OPEC plans oil production adjustment", "published": "2026-10-25T12:00:00Z"}], NOW)
        self.assertEqual(data["articles"][0]["markets"], ["BRENT", "WTI"])
        self.assertIn("ENERGY_SUPPLY", data["articles"][0]["topics"])

    def test_old_unknown_and_future_timestamps(self):
        rows = [
            {"title": "Gold market outlook", "published": "2026-10-01T00:00:00Z"},
            {"title": "Forex currency outlook", "published": "2026-10-26 10:00:00"},
            {"title": "ECB rate decision scheduled", "published": "2026-10-28T04:00:00Z"}
        ]
        articles = mod.classify(rows, NOW)["articles"]
        by_title = {x["title"]: x for x in articles}
        self.assertEqual(by_title["Gold market outlook"]["freshness"], "STALE")
        self.assertEqual(by_title["Forex currency outlook"]["freshness"], "UNKNOWN")
        self.assertEqual(by_title["ECB rate decision scheduled"]["freshness"], "UNKNOWN")
        self.assertFalse(by_title["ECB rate decision scheduled"]["verifiedScheduledEvent"])

    def test_duplicate_title_merges_source_not_multiple_votes(self):
        rows = [{"title": "Gold rises on inflation worries", "source": source, "published": "2026-10-26T01:00:00Z"}
                for source in ("feed-1", "feed-2", "feed-1")]
        data = mod.classify(rows, NOW)
        self.assertEqual(data["articleCount"], 1)
        self.assertEqual(data["articles"][0]["sources"], ["feed-1", "feed-2"])

    def test_out_of_scope_is_filtered(self):
        data = mod.classify([{"title": "Football game postponed"}], NOW)
        self.assertEqual(data["articleCount"], 0)
        self.assertEqual(data["hardNewsClearance"], "NEWS_UNVERIFIED")

    def test_rss_atom_extraction(self):
        rss = b"<rss><channel><item><title>WTI crude oil inventory report</title><pubDate>Mon, 26 Oct 2026 03:00:00 +0000</pubDate><link>https://example.org/r</link></item></channel></rss>"
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>ECB rate decision</title><published>2026-10-26T03:00:00Z</published><link href="https://example.org/a"/></entry></feed>'
        self.assertEqual(mod.parse_feed(rss, "rss")[0]["source"], "rss")
        self.assertEqual(mod.parse_feed(atom, "atom")[0]["url"], "https://example.org/a")
        self.assertEqual(mod.parse_feed(rss, "rss")[0]["published"], "Mon, 26 Oct 2026 03:00:00 +0000")

    def test_feed_host_rejects_non_allowlisted_or_http_before_request(self):
        for url in ("http://www.eia.gov/rss", "https://localhost/rss", "https://example.org/rss",
                    "https://www.eia.gov.evil.invalid/rss"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                mod.fetch_feed(url)

    def test_cli_offline_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.json"
            input_path.write_text(json.dumps([{"title": "Fed interest rate decision", "published": "2026-10-26T02:00:00Z"}]))
            status = mod.main(["--input-json", str(input_path), "--now", "2026-10-26T04:00:00Z", "--output", str(output_path)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output_path.read_text())["hardNewsClearance"], "NEWS_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
