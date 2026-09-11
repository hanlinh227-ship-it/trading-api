import json
import tempfile
import unittest
from pathlib import Path

from stackhub.stackhub.cli import main


class CliTests(unittest.TestCase):
    def test_sources_command_returns_registered_sources(self):
        result = main(["sources", "--environment", "vps"])
        names = {item["slug"] for item in result["sources"]}
        self.assertIn("grass", names)
        self.assertIn("jumptask", names)

    def test_opportunities_filters_deposit_and_ranks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "opportunities.json"
            path.write_text(json.dumps([
                {"source":"a","title":"slow","expected_reward_usd":1,"estimated_minutes":10},
                {"source":"b","title":"fast","expected_reward_usd":0.5,"estimated_minutes":2},
                {"source":"c","title":"deposit","expected_reward_usd":50,"estimated_minutes":1,"requires_deposit":True}
            ]), encoding="utf-8")
            result = main(["opportunities", "--file", str(path)])
            self.assertEqual([x["title"] for x in result["opportunities"]], ["fast", "slow"])

    def test_record_and_status_share_persistent_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "ledger.sqlite3")
            main(["record", "--db", db, "--source", "golem", "--usd", "0.25", "--asset", "GLM", "--amount", "1.0", "--timestamp", "2026-09-11T12:00:00Z"])
            status = main(["status", "--db", db, "--environment", "vps"])
            self.assertEqual(status["ledger"]["entries"], 1)
            self.assertAlmostEqual(status["ledger"]["total_usd"], 0.25)


if __name__ == "__main__":
    unittest.main()
