import tempfile
import unittest
from pathlib import Path

from stackhub.stackhub.ledger import Ledger


class LedgerTests(unittest.TestCase):
    def test_records_and_sums_earnings_persistently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "earnings.sqlite3"
            ledger = Ledger(path)
            ledger.record("golem", 0.30, "GLM", 1.2, "2026-09-11T12:00:00Z")
            ledger.record("grass", 0.20, "USDC", 0.2, "2026-09-11T12:10:00Z")
            reopened = Ledger(path)
            summary = reopened.summary()
            self.assertAlmostEqual(summary["total_usd"], 0.50)
            self.assertEqual(summary["entries"], 2)
            self.assertAlmostEqual(summary["assets"]["GLM"], 1.2)
            self.assertAlmostEqual(summary["assets"]["USDC"], 0.2)

    def test_negative_earning_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / "earnings.sqlite3")
            with self.assertRaises(ValueError):
                ledger.record("x", -1.0, "BTC", 0.0, "2026-09-11T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
