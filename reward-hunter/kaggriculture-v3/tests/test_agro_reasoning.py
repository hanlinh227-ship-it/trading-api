import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agro_reasoning import (
    PUBLIC_META_PRIORS,
    agro_penalty,
    dominant_failures,
    observe_agro_evaluation,
    recovery_patches,
    strategy_family,
)
from learning_rank import blank_state
from policy import validate_params


class AgroReasoningTests(unittest.TestCase):
    def row(self, margin=-5000, money=18000, animals=10, plants=4, structures=12,
            unlock=4, util=.45, unsold=12, noops=0, moves=30, actions=100, valid=True):
        return {
            'valid': valid,
            'margin': margin,
            'candidate_money': money,
            'terminal_unsold_units': unsold,
            'final_unlocked_quadrants': unlock,
            'final_animals': animals,
            'final_plants': plants,
            'final_structures': structures,
            'peak_productive_utilization': util,
            'efficiency': {'actions': actions, 'moves': moves, 'passes': 0, 'noops': noops},
        }

    def test_public_meta_priors_are_valid_parameter_patches(self):
        self.assertGreaterEqual(len(PUBLIC_META_PRIORS), 3)
        for patch in PUBLIC_META_PRIORS:
            p = validate_params(patch)
            self.assertEqual(p['land_target_quadrants'], 3)
            self.assertGreaterEqual(p['cow_max'], 8)
            self.assertLessEqual(p['sell_batch'], 5)

    def test_loss_is_decomposed_into_farming_reasons(self):
        state = blank_state()
        p = validate_params({
            'land_target_quadrants': 4,
            'target_hands': 13,
            'cow_max': 9,
            'sheep_max': 5,
            'feed_carry': 4,
            'sell_batch': 10,
            'crop_mode': 'fast_cash',
        })
        state = observe_agro_evaluation(state, p, {'rows': [self.row()]}, 'bad-economics')
        reasons = dict(dominant_failures(state, 20))
        self.assertIn('fourth_quadrant_overreach', reasons)
        self.assertIn('labor_overhead', reasons)
        self.assertIn('herd_feed_pressure', reasons)
        self.assertIn('premium_glut_dumping', reasons)
        self.assertIn('volume_over_value', reasons)
        self.assertIn('terminal_inventory', reasons)

    def test_repeated_failure_generates_new_recovery_hypotheses(self):
        state = blank_state()
        p = validate_params({
            'land_target_quadrants': 4,
            'target_hands': 13,
            'cow_max': 9,
            'sheep_max': 5,
            'feed_carry': 4,
            'sell_batch': 10,
            'crop_mode': 'fast_cash',
        })
        for i in range(2):
            state = observe_agro_evaluation(state, p, {'rows': [self.row(margin=-6000-i*100)]}, 'loss-%d' % i)
        patches = recovery_patches(state, p, 12)
        self.assertTrue(any(x.get('land_target_quadrants') == 3 for x in patches))
        self.assertTrue(any(x.get('feed_carry') == 8 for x in patches))
        self.assertTrue(any(x.get('sell_batch') <= 5 for x in patches))
        self.assertTrue(any(x.get('crop_mode') in ('roi', 'demand', 'grains') for x in patches))

    def test_failed_family_is_soft_penalized_not_globally_banned(self):
        state = blank_state()
        bad = validate_params({'land_target_quadrants': 4, 'target_hands': 13, 'cow_max': 9, 'sheep_max': 5, 'sell_batch': 10})
        good = validate_params({'land_target_quadrants': 3, 'target_hands': 10, 'cow_max': 9, 'sheep_max': 4, 'sell_batch': 4})
        for i in range(3):
            state = observe_agro_evaluation(state, bad, {'rows': [self.row(margin=-7000-i)]}, 'bad-%d' % i)
        self.assertGreater(agro_penalty(state, bad), agro_penalty(state, good))
        self.assertNotEqual(strategy_family(bad), strategy_family(good))

    def test_wins_remain_positive_evidence(self):
        state = blank_state()
        p = validate_params({'land_target_quadrants': 3, 'cow_max': 9, 'sheep_max': 4, 'sell_batch': 4})
        row = self.row(margin=9000, money=52000, animals=12, plants=8, structures=12,
                       unlock=3, util=.82, unsold=2)
        state = observe_agro_evaluation(state, p, {'rows': [row]}, 'win')
        fam = state['agro_reasoning']['families'][strategy_family(p)]
        self.assertEqual(fam['win'], 1)
        self.assertEqual(fam['fail'], 0)


if __name__ == '__main__':
    unittest.main()
