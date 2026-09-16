from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/deploy-skill-mandatory-fast-gateway.yml"


class AutopilotDeployRouteMatrixTests(unittest.TestCase):
    def test_market_scan_canaries_track_canonical_multi_market_owner(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        expected = [
            "check_route_eventually 'quét market BTC live' multi_market_analysis DEEP",
            "verify_live_plan 'quét market BTC live' multi_market_analysis DEEP 4",
        ]
        stale = [
            "check_route_eventually 'quét market BTC live' trading_router DEEP",
            "verify_live_plan 'quét market BTC live' trading_router DEEP 4",
        ]
        for contract in expected:
            self.assertIn(contract, text)
        for contract in stale:
            self.assertNotIn(contract, text)


if __name__ == "__main__":
    unittest.main()
