import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_rank import blank_state
from monotonic_rank import (
    accepted_params,
    decide_and_record,
    failure_penalty,
    is_taboo,
    record_monotonic_round,
    summary,
)
from policy import validate_params


class MonotonicRankTests(unittest.TestCase):
    def metrics(self, money=50000, margin=12000, win=.8, worst=1000, catastrophic=0, unsold=4, noop=0):
        return {
            'mean_money': money,
            'mean_margin': margin,
            'win_rate': win,
            'worst_margin': worst,
            'catastrophic_rate': catastrophic,
            'mean_terminal_unsold_units': unsold,
            'noop_rate': noop,
        }

    def pack(self, **kw):
        m = self.metrics(**kw)
        return {'duel': dict(m), 'holdout': dict(m), 'final': dict(m)}

    def test_bootstrap_establishes_research_champion(self):
        state = blank_state()
        p = validate_params({'land_target_quadrants': 3, 'cow_max': 9, 'sheep_max': 4})
        state, decision = decide_and_record(state, p, self.pack(money=50000), None, 'bootstrap')
        self.assertTrue(decision['pass'])
        self.assertTrue(decision['improved'])
        self.assertEqual(accepted_params(state), p)
        self.assertEqual(summary(state)['accepted_count'], 1)

    def test_lower_money_is_rejected_and_exact_strategy_becomes_taboo(self):
        state = blank_state()
        incumbent = validate_params({'land_target_quadrants': 3, 'cow_max': 9, 'sheep_max': 4})
        challenger = validate_params({'land_target_quadrants': 3, 'cow_max': 7, 'sheep_max': 6})
        state, _ = decide_and_record(state, incumbent, self.pack(money=50000), None, 'base')
        state, decision = decide_and_record(
            state, challenger, self.pack(money=49000), self.pack(money=50000), 'loss'
        )
        self.assertFalse(decision['pass'])
        self.assertIn('money_not_above_incumbent', decision['reasons'])
        self.assertTrue(is_taboo(state, challenger))
        self.assertEqual(accepted_params(state), incumbent)
        self.assertEqual(summary(state)['rejected_count'], 1)

    def test_more_money_cannot_hide_margin_or_tail_regression(self):
        state = blank_state()
        base = validate_params({'land_target_quadrants': 3, 'cow_max': 9})
        challenger = validate_params({'land_target_quadrants': 3, 'cow_max': 10})
        state, _ = decide_and_record(state, base, self.pack(money=50000, margin=12000, worst=1000), None, 'base')
        worse = self.pack(money=54000, margin=11000, worst=-500)
        state, decision = decide_and_record(state, challenger, worse, self.pack(money=50000, margin=12000, worst=1000), 'bad-risk')
        self.assertFalse(decision['pass'])
        self.assertIn('holdout_margin_regression', decision['reasons'])
        self.assertIn('tail_regression', decision['reasons'])
        self.assertEqual(accepted_params(state), base)

    def test_strictly_better_paired_strategy_replaces_champion(self):
        state = blank_state()
        base = validate_params({'land_target_quadrants': 3, 'cow_max': 8, 'sheep_max': 4})
        better = validate_params({'land_target_quadrants': 3, 'cow_max': 9, 'sheep_max': 4})
        state, _ = decide_and_record(state, base, self.pack(money=50000, margin=11000), None, 'base')
        state, decision = decide_and_record(
            state, better,
            self.pack(money=51500, margin=12500, win=.85, worst=1500, unsold=3),
            self.pack(money=50000, margin=11000, win=.8, worst=1000, unsold=4),
            'better',
        )
        self.assertTrue(decision['pass'])
        self.assertGreater(decision['money_gain'], 0)
        self.assertEqual(accepted_params(state), better)
        self.assertGreaterEqual(summary(state)['money_high_water'], 51500)

    def test_rejected_round_is_not_archived_and_forces_recovery(self):
        state = blank_state()
        base = validate_params({'land_target_quadrants': 3, 'cow_max': 9})
        bad = validate_params({'land_target_quadrants': 4, 'cow_max': 5})
        state, _ = decide_and_record(state, base, self.pack(money=50000), None, 'base')
        state, decision = decide_and_record(state, bad, self.pack(money=47000), self.pack(money=50000), 'bad')
        state = record_monotonic_round(
            state, bad,
            self.metrics(money=47000), self.metrics(money=47000), self.metrics(money=47000),
            {'pass_gate': False}, decision, 'bad',
        )
        self.assertEqual(state['control']['stagnation'], 1)
        self.assertEqual(state['control']['regressions'], 1)
        self.assertTrue(all(x.get('params') != bad for x in state.get('champions', [])))

    def test_repeated_failed_values_gain_penalty_but_new_combinations_remain_possible(self):
        state = blank_state()
        base = validate_params({'land_target_quadrants': 3, 'cow_max': 9})
        state, _ = decide_and_record(state, base, self.pack(money=50000), None, 'base')
        for i, cows in enumerate((5, 6)):
            p = validate_params({'land_target_quadrants': 4, 'cow_max': cows, 'target_hands': 13})
            state, _ = decide_and_record(state, p, self.pack(money=45000-i*500), self.pack(money=50000), 'fail-%d' % i)
        fresh = validate_params({'land_target_quadrants': 4, 'cow_max': 8, 'target_hands': 13})
        self.assertFalse(is_taboo(state, fresh))
        self.assertGreater(failure_penalty(state, fresh), 0)


if __name__ == '__main__':
    unittest.main()
