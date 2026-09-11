import unittest

from stackhub.stackhub.compliance import can_auto_run
from stackhub.stackhub.models import AutomationClass, SourcePolicy
from stackhub.stackhub.registry import get_sources


class ComplianceTests(unittest.TestCase):
    def test_human_required_never_auto_runs(self):
        source = SourcePolicy(
            name="Manual Survey",
            automation_class=AutomationClass.HUMAN_REQUIRED,
            payout_assets=("USDC",),
        )
        allowed, reason = can_auto_run(source, environment="residential")
        self.assertFalse(allowed)
        self.assertIn("human", reason.lower())

    def test_residential_only_source_is_blocked_on_vps(self):
        pawns = next(source for source in get_sources() if source.slug == "pawns")
        allowed, reason = can_auto_run(pawns, environment="vps")
        self.assertFalse(allowed)
        self.assertIn("residential", reason.lower())

    def test_registry_uses_known_automation_classes(self):
        for source in get_sources():
            self.assertIsInstance(source.automation_class, AutomationClass)


if __name__ == "__main__":
    unittest.main()
