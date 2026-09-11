import unittest

from stackhub.stackhub.status import build_status


class StatusTests(unittest.TestCase):
    def test_status_redacts_secret_like_fields(self):
        status = build_status(
            environment="vps",
            ledger_summary={"total_usd": 1.25, "entries": 2, "assets": {"GLM": 3}},
            extra={"api_token": "secret", "wallet_seed": "never-print", "healthy": True},
        )
        serialized = repr(status).lower()
        self.assertNotIn("secret", serialized)
        self.assertNotIn("never-print", serialized)
        self.assertEqual(status["extra"]["api_token"], "[REDACTED]")
        self.assertEqual(status["extra"]["wallet_seed"], "[REDACTED]")
        self.assertTrue(status["extra"]["healthy"])


if __name__ == "__main__":
    unittest.main()
