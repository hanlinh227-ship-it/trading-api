import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_rank import (
    blank_state, load_state, save_state, observe_evaluation, value_score, learned_variants,
    weak_families, adaptive_plan, record_round, champion_params,
)
from policy import validate_params
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

    def metrics(self, margin=5000, win_rate=1.0, worst=1000, unsold=4, catastrophic=0.0):
        return {
            'mean_margin': margin,
            'win_rate': win_rate,
            'worst_margin': worst,
            'mean_terminal_unsold_units': unsold,
            'catastrophic_rate': catastrophic,
        }

    def test_wins_and_losses_both_change_learning(self):
        state = blank_state()
        good = validate_params({'land_target_quadrants': 3, 'cow_max': 9})
        bad = validate_params({'land_target_quadrants': 4, 'cow_max': 5})
        state = observe_evaluation(state, good, {'rows': [self.row(6000), self.row(2500, seat=1)]}, 'good')
        state = observe_evaluation(state, bad, {'rows': [self.row(-7000), self.row(-3000, seat=1)]}, 'bad')
        self.assertEqual(state['matches'], 4)
        self.assertEqual(state['wins'], 2)
        self.assertEqual(state['losses'], 2)
        self.assertGreater(value_score(state, 'land_target_quadrants', 3), value_score(state, 'land_target_quadrants', 4))

    def test_family_conditioned_learning_targets_weakness(self):
        state = blank_state()
        p3 = validate_params({'land_target_quadrants': 3})
        p4 = validate_params({'land_target_quadrants': 4})
        state = observe_evaluation(state, p3, {'rows': [self.row(-6500, opponent='expansion'), self.row(5500, opponent='starter')]}, 'p3')
        state = observe_evaluation(state, p4, {'rows': [self.row(5000, opponent='expansion'), self.row(3000, opponent='starter')]}, 'p4')
        self.assertEqual(weak_families(state, limit=1), ['expansion'])
        self.assertGreater(
            value_score(state, 'land_target_quadrants', 4, ['expansion']),
            value_score(state, 'land_target_quadrants', 3, ['expansion'])
        )

    def test_invalid_noop_and_inventory_are_penalized(self):
        state = blank_state()
        p = validate_params({})
        state = observe_evaluation(state, p, {'rows': [self.row(-1, valid=False), self.row(-400, unsold=40, noops=6)]}, 'losses')
        self.assertEqual(state['invalid'], 1)
        self.assertIn('invalid', state['signals'])
        self.assertIn('unit_noop', state['signals'])
        self.assertIn('terminal_inventory', state['signals'])

    def test_state_round_trip_migrates_old_cache_without_reset(self):
        state = blank_state()
        state = observe_evaluation(state, validate_params({}), {'rows': [self.row(1000)]}, 'one')
        state.pop('conditional_values')
        state.pop('champions')
        state.pop('round_history')
        state.pop('control')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'state.json'
            p.write_text(json.dumps(state))
            loaded = load_state(p)
            self.assertEqual(loaded['matches'], 1)
            self.assertEqual(loaded['wins'], 1)
            self.assertIn('conditional_values', loaded)
            self.assertIn('champions', loaded)
            save_state(p, loaded)
            self.assertTrue(json.loads(p.read_text())['updated_at'])

    def test_learned_variants_are_valid_and_unique(self):
        state = blank_state()
        elite = validate_params({'land_target_quadrants': 3, 'cow_max': 9, 'sheep_max': 4})
        state = observe_evaluation(state, elite, {'rows': [self.row(5000), self.row(3000, seat=1)]}, 'elite')
        out = learned_variants([elite], state, CHOICES, validate_params, random.Random(7), 4,
                               focus_families=['incumbent'], exploration=.30, mutation_steps=3)
        self.assertEqual(len(out), 4)
        self.assertEqual(len({json.dumps(x, sort_keys=True) for x in out}), 4)
        for p in out:
            self.assertEqual(p, validate_params(p))

    def test_stagnation_expands_search_and_elite_archive_survives(self):
        state = blank_state()
        p1 = validate_params({'land_target_quadrants': 3, 'cow_max': 9})
        strong = self.metrics(9000, 1.0, 2500, 3)
        state = record_round(state, p1, strong, strong, strong, {'pass_gate': False}, 'r1')
        self.assertEqual(champion_params(state, 1)[0], p1)
        # Repeating materially the same performance creates stagnation and broadens the next search.
        state = record_round(state, p1, strong, strong, strong, {'pass_gate': False}, 'r2')
        state = record_round(state, p1, strong, strong, strong, {'pass_gate': False}, 'r3')
        plan = adaptive_plan(state, 24)
        self.assertGreaterEqual(plan['candidate_count'], 40)
        self.assertGreaterEqual(plan['mutation_steps'], 3)
        self.assertGreaterEqual(plan['exploration'], .32)

    def test_periodic_deep_round_forces_diversification(self):
        state = blank_state()
        state['control']['rounds'] = 4
        plan = adaptive_plan(state, 24)
        self.assertEqual(plan['mode'], 'periodic-deep')
        self.assertGreaterEqual(plan['candidate_count'], 48)
        self.assertGreaterEqual(plan['mutation_steps'], 3)


if __name__ == '__main__':
    unittest.main()
