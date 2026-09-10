import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from policy import (
    _animal_roi,
    _animal_targets,
    _fertilize_is_worth_it,
    _target_land_reached,
    make_v3,
    validate_params,
)
from features import features


class RankLivestockTests(unittest.TestCase):
    def obs(self, seed=777):
        from kaggle_environments import make
        e = make('kaggriculture', configuration={'seed': seed})
        e.reset(2)
        return e.state[0].observation, e.configuration

    def test_land_target_is_explicit_and_bounded(self):
        self.assertEqual(validate_params({'land_target_quadrants': 3})['land_target_quadrants'], 3)
        with self.assertRaises(ValueError):
            validate_params({'land_target_quadrants': 2})
        self.assertTrue(_target_land_reached({'unlocked_quadrants': 3}, validate_params({'land_target_quadrants': 3})))
        self.assertFalse(_target_land_reached({'unlocked_quadrants': 3}, validate_params({'land_target_quadrants': 4})))

    def test_fertilizer_has_real_market_ratio(self):
        o, c = self.obs()
        o.market['prices']['FERTILIZER'] = 150
        f = features(o, c)
        self.assertAlmostEqual(f['price_ratios']['FERTILIZER'], 1.5)

    def test_surplus_fertilizer_is_monetized(self):
        o, c = self.obs()
        o.private['shed']['FERTILIZER'] = 8
        o.market['prices']['FERTILIZER'] = 100
        a = make_v3({'fertilizer_reserve': 2})(o, c)
        fert_sales = [x for x in a['market'] if x[:2] == ['SELL', 'FERTILIZER']]
        self.assertTrue(fert_sales, a['market'])
        self.assertGreaterEqual(fert_sales[0][2], 3)

    def test_late_animals_are_rejected_by_horizon(self):
        o, c = self.obs()
        o.day = 25
        o.hour = 0
        f = features(o, c)
        p = validate_params({'herd_mode': 'dynamic', 'cow_max': 9, 'sheep_max': 5})
        self.assertLess(_animal_roi('COW', f, p), 0)
        self.assertEqual(_animal_targets(f, p)['COW'], 0)

    def test_high_value_fertilization_beats_sale(self):
        o, c = self.obs()
        o.market['prices']['FERTILIZER'] = 70
        o.market['prices']['TOMATO'] = 90
        f = features(o, c)
        self.assertTrue(_fertilize_is_worth_it('TOMATO', f))
        o.market['prices']['FERTILIZER'] = 200
        o.market['prices']['TOMATO'] = 30
        f = features(o, c)
        self.assertFalse(_fertilize_is_worth_it('TOMATO', f))


if __name__ == '__main__':
    unittest.main()
