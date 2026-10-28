import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from market_intelligence_v1 import build_research, fx_strength


class MarketIntelTests(unittest.TestCase):
    def test_breadth_is_low_for_top3(self):
        res = fx_strength([{"symbol": "EURUSD", "technicalBias": "BUY"},
                           {"symbol": "USDJPY", "technicalBias": "SELL"}])
        self.assertEqual(res["coverage"], "LOW")
        self.assertIsNone(res["strength"]["USD"])

    def test_stale_sends_hold_no_execution(self):
        fx = {"updatedAt": "2026-08-17T00:00:00Z", "pairsScanned": 28,
              "top3": [{"symbol": "EURUSD", "technicalBias": "BUY",
                        "frameDirection": {"H4": "BUY", "H1": "BUY", "M5": "BUY"}}]}
        crypto = {"updatedAt": "2026-08-17T00:00:00Z", "broadAnalyzed": 57,
                  "top": [{"symbol": "BTC", "side": "LONG",
                           "H1": {"ema20": 2, "ema50": 1}}]}
        report = build_research(fx, crypto, datetime(2026, 10, 28, tzinfo=timezone.utc))
        self.assertFalse(report["executionAuthorized"])
        self.assertEqual(report["forex"]["quality"]["status"], "DELAYED")
        self.assertEqual(report["crypto"]["fullMarketBreadth"], "UNAVAILABLE_TOP5_NOT_FULL_UNIVERSE")
        self.assertEqual(report["forex"]["candidates"][0]["decision"], "HOLD")
        self.assertEqual(report["crypto"]["candidates"][0]["decision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
