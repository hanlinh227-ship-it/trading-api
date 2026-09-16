from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/deploy-skill-mandatory-fast-gateway.yml"


class AutopilotDeployRouteMatrixTests(unittest.TestCase):
    def test_market_scan_canary_tracks_canonical_multi_market_owner(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "check_route_eventually 'quét market BTC live' multi_market_analysis DEEP",
            text,
        )
        self.assertNotIn(
            "check_route_eventually 'quét market BTC live' trading_router DEEP",
            text,
        )


if __name__ == "__main__":
    unittest.main()
