import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_rank import blank_state, load_state, save_state, observe_evaluation, value_score, learned_variants
from policy import V3_DEFAULT, validate_params
from search_rank import CHOICES


class LearningRankTests(unittest.TestCase):
    def row(self, margin, opponent='incumbent', seat=0, valid=True, unsold=0, noops=0):
        return {
            'valid': valid,
            'margin': margin,
            'opponent': opponent,
            'seat': seat,
            'terminal_unsold_units': unsold,
            'peak_animals': 8,
            'efficiency': {'actions': 100, 'moves': 10, 'passes': 2, 'noops': noops},
        }

    def test_wins_and_losses_both_change_learning(self):
        state = blank_state()
        good = validate_params({'land_target_quadrants': 3, 'cow_max': 9})
        bad = validate_params({'land_target_quadrants': 4, 'cow_max': 5})
        observe_evaluation(state, good, {'rows': [self.row(6000), self.row(2500, seat=1)]}, 'good')
        observe_evaluation(state, bad, {'rows': [self.row(-7000), self.row(-3000, seat=1)]}, 'bad')
        self.assertEqual(state['matches'], 4)
        self.assertEqual(state['wins'], 2)
        self.assertEqual(state['losses'], 2)
        self.assertGreater(value_score(state, 'land_target_quadrants', 3), value_score(state, 'land_target_quadrants', 4))

    def test_invalid_noop_and_inventory_are_penalized(self):
        state = blank_state()
        p = validate_params({})
        observe_evaluation(state, p, {'rows': [self.row(-1, valid=False), self.row(-400, unsold=40, noops=6)]}, 'losses')
        self.assertEqual(state['invalid'], 1)
        self.assertIn('invalid', state['signals'])
        self.assertIn('unit_noop', state['signals'])
        self.assertIn('terminal_inventory', state['signals'])

    def test_state_round_trip_is_atomic_and_reusable(self):
        state = blank_state()
        observe_evaluation(state, validate_params({}), {'rows': [self.row(1000)]}, 'one')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'state.json'
            save_state(p, state)
            loaded = load_state(p)
            self.assertEqual(loaded['matches'], 1)
            self.assertEqual(loaded['wins'], 1)
            self.assertTrue(json.loads(p.read_text())['updated_at'])

    def test_learned_variants_are_valid_and_unique(self):
        state = blank_state()
        elite = validate_params({'land_target_quadrants': 3, 'cow_max': 9, 'sheep_max': 4})
        observe_evaluation(state, elite, {'rows': [self.row(5000), self.row(3000, seat=1)]}, 'elite')
        out = learned_variants([elite], state, CHOICES, validate_params, random.Random(7), 4)
        self.assertEqual(len(out), 4)
        self.assertEqual(len({json.dumps(x, sort_keys=True) for x in out}), 4)
        for p in out:
            self.assertEqual(p, validate_params(p))


if __name__ == '__main__':
    unittest.main()
