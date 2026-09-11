import unittest

from stackhub.stackhub.models import Opportunity
from stackhub.stackhub.ranker import rank_opportunities, score_opportunity


class RankerTests(unittest.TestCase):
    def test_deposit_required_is_rejected(self):
        item = Opportunity("x", "deposit", 10, 1, requires_deposit=True)
        self.assertEqual(score_opportunity(item), float("-inf"))

    def test_ranking_prefers_expected_value_per_minute(self):
        slow = Opportunity("a", "slow", 1.0, 10, approval_probability=1.0)
        fast = Opportunity("b", "fast", 0.5, 2, approval_probability=1.0)
        ranked = rank_opportunities([slow, fast])
        self.assertEqual([item.title for item in ranked], ["fast", "slow"])

    def test_ranking_is_deterministic_on_tie(self):
        b = Opportunity("b", "B", 1, 2)
        a = Opportunity("a", "A", 1, 2)
        ranked = rank_opportunities([b, a])
        self.assertEqual([item.source for item in ranked], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
