"""Domain reasoning for crop/livestock failures and recovery.

This module turns local episode mistakes into farming hypotheses instead of treating every
loss as an opaque scalar.  It only consumes our own current-engine evaluation telemetry and
publicly documented game mechanics / public meta priors.  It never reads hidden Kaggle state.

The goal is not to copy one historical top trajectory.  Public top patterns are used as priors,
then personalized by our own win/loss memory and monotonic capital gate.
"""
from __future__ import annotations

import json
import math

# Public meta priors observed in high-Elo public replays/discussions.  These are deliberately
# parameter-level priors, not copied action tapes.  The search is free to reject all of them.
PUBLIC_META_PRIORS = (
    {
        'land_target_quadrants': 3, 'herd_mode': 'cow_sheep', 'cow_max': 9,
        'sheep_max': 4, 'goose_max': 0, 'target_hands': 10, 'livestock_start_day': 0,
        'crop_mode': 'roi', 'feed_carry': 8, 'sell_batch': 4,
        'fertilizer_mode': 'adaptive', 'fertilizer_reserve': 1,
    },
    {
        'land_target_quadrants': 3, 'herd_mode': 'cow_sheep', 'cow_max': 9,
        'sheep_max': 5, 'goose_max': 0, 'target_hands': 9, 'livestock_start_day': 0,
        'crop_mode': 'demand', 'feed_carry': 8, 'sell_batch': 5,
        'fertilizer_mode': 'adaptive', 'fertilizer_reserve': 1,
    },
    {
        'land_target_quadrants': 3, 'herd_mode': 'cow_sheep', 'cow_max': 9,
        'sheep_max': 4, 'goose_max': 0, 'target_hands': 10, 'livestock_start_day': 0,
        'crop_mode': 'grains', 'feed_carry': 8, 'sell_batch': 5,
        'seed_scale': 1.7, 'fertilizer_mode': 'adaptive', 'fertilizer_reserve': 1,
    },
)

MAX_AGRO_EVENTS = 192
MAX_REASON_VALUES = 64


def _bucket(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _ensure(state):
    agro = state.setdefault('agro_reasoning', {})
    agro.setdefault('events', 0)
    agro.setdefault('loss_events', 0)
    agro.setdefault('win_events', 0)
    agro.setdefault('reasons', {})
    agro.setdefault('families', {})
    agro.setdefault('reason_values', {})
    agro.setdefault('successful_values', {})
    agro.setdefault('recent', [])
    for key in ('reasons', 'families', 'reason_values', 'successful_values'):
        if not isinstance(agro.get(key), dict):
            agro[key] = {}
    if not isinstance(agro.get('recent'), list):
        agro['recent'] = []
    return state


def strategy_family(params):
    herd = int(params.get('cow_max', 0) or 0) + int(params.get('sheep_max', 0) or 0) + int(params.get('goose_max', 0) or 0)
    if params.get('herd_mode') == 'none' or herd <= 0:
        production = 'crop_only'
    elif int(params.get('goose_max', 0) or 0) >= 2:
        production = 'mixed_goose'
    elif int(params.get('cow_max', 0) or 0) >= 8:
        production = 'cow_heavy'
    elif int(params.get('sheep_max', 0) or 0) >= 5:
        production = 'sheep_heavy'
    else:
        production = 'balanced_livestock'
    land = '%sQ' % int(params.get('land_target_quadrants', 4) or 4)
    labor = 'high_labor' if int(params.get('target_hands', 0) or 0) >= 12 else ('lean_labor' if int(params.get('target_hands', 0) or 0) <= 9 else 'mid_labor')
    market = 'large_batch' if int(params.get('sell_batch', 0) or 0) >= 8 else ('small_batch' if int(params.get('sell_batch', 0) or 0) <= 5 else 'mid_batch')
    return '|'.join((land, production, labor, market, str(params.get('crop_mode', 'roi'))))


def _diagnose_row(row, params):
    reasons = []
    valid = bool(row.get('valid'))
    margin = float(row.get('margin', 0.0) or 0.0)
    money = float(row.get('candidate_money', 0.0) or 0.0)
    unsold = float(row.get('terminal_unsold_units', 0.0) or 0.0)
    eff = row.get('efficiency') or {}
    noops = int(eff.get('noops', 0) or 0)
    moves = int(eff.get('moves', 0) or 0)
    actions = max(1, int(eff.get('actions', 0) or 0))
    unlock = int(row.get('final_unlocked_quadrants', 1) or 1)
    plants = int(row.get('final_plants', 0) or 0)
    animals = int(row.get('final_animals', 0) or 0)
    structures = int(row.get('final_structures', 0) or 0)
    peak_productive = float(row.get('peak_productive_utilization', 0.0) or 0.0)

    target_herd = int(params.get('cow_max', 0) or 0) + int(params.get('sheep_max', 0) or 0) + int(params.get('goose_max', 0) or 0)
    high_premium_herd = int(params.get('cow_max', 0) or 0) + int(params.get('sheep_max', 0) or 0)

    if not valid:
        reasons.append('invalid_execution')
    if noops > 0:
        reasons.append('action_waste')
    if unsold > 8:
        reasons.append('terminal_inventory')
    if moves / actions > .70:
        reasons.append('routing_overhead')
    if peak_productive and peak_productive < .55 and unlock >= 3:
        reasons.append('underutilized_land')
    if int(params.get('land_target_quadrants', 4) or 4) >= 4 and unlock >= 4 and (margin < 0 or peak_productive < .62):
        reasons.append('fourth_quadrant_overreach')
    if int(params.get('target_hands', 0) or 0) >= 12 and margin < 0:
        reasons.append('labor_overhead')
    if target_herd >= 11 and int(params.get('feed_carry', 0) or 0) <= 5 and margin < 0:
        reasons.append('herd_feed_pressure')
    if target_herd >= 10 and animals < max(3, int(target_herd * .45)) and margin < 0:
        reasons.append('herd_capital_not_converted')
    if high_premium_herd >= 10 and int(params.get('sell_batch', 0) or 0) >= 8 and margin <= 0:
        reasons.append('premium_glut_dumping')
    if params.get('crop_mode') == 'fast_cash' and int(params.get('sell_batch', 0) or 0) >= 8 and margin < 0:
        reasons.append('volume_over_value')
    if params.get('herd_mode') == 'none' and margin < 0 and money < 30000:
        reasons.append('crop_only_income_ceiling')
    if animals >= 6 and plants < max(4, animals // 2) and params.get('crop_mode') != 'grains' and margin < 0:
        reasons.append('livestock_without_crop_support')
    if structures > animals + 3 and margin < 0:
        reasons.append('idle_structure_capital')
    if margin < -5000:
        reasons.append('catastrophic_economics')
    return reasons


def _update_value(table, key, value, amount=1):
    by_key = table.setdefault(str(key), {})
    bucket = _bucket(value)
    by_key[bucket] = int(by_key.get(bucket, 0) or 0) + int(amount)


def observe_agro_evaluation(state, params, evaluation, label=''):
    """Learn domain failure/success patterns from every local game row."""
    state = _ensure(state)
    agro = state['agro_reasoning']
    family = strategy_family(params)
    for row in evaluation.get('rows', []):
        agro['events'] += 1
        margin = float(row.get('margin', 0.0) or 0.0)
        reasons = _diagnose_row(row, params)
        if reasons or margin < 0 or not row.get('valid'):
            agro['loss_events'] += 1
            fstat = agro['families'].setdefault(family, {'fail': 0, 'win': 0})
            fstat['fail'] = int(fstat.get('fail', 0) or 0) + 1
            for reason in reasons or ('unclassified_loss',):
                agro['reasons'][reason] = int(agro['reasons'].get(reason, 0) or 0) + 1
                rv = agro['reason_values'].setdefault(reason, {})
                for key, value in params.items():
                    if isinstance(value, dict):
                        continue
                    _update_value(rv, key, value)
            agro['recent'].append({'label': str(label), 'family': family, 'margin': margin, 'reasons': list(reasons or ('unclassified_loss',))})
        else:
            agro['win_events'] += 1
            fstat = agro['families'].setdefault(family, {'fail': 0, 'win': 0})
            fstat['win'] = int(fstat.get('win', 0) or 0) + 1
            for key, value in params.items():
                if isinstance(value, dict):
                    continue
                _update_value(agro['successful_values'], key, value)
    agro['recent'] = agro['recent'][-MAX_AGRO_EVENTS:]
    return state


def dominant_failures(state, limit=6):
    state = _ensure(state)
    items = sorted(state['agro_reasoning']['reasons'].items(), key=lambda kv: (int(kv[1]), kv[0]), reverse=True)
    return items[:max(0, int(limit))]


def agro_penalty(state, params):
    """Softly avoid repeatedly failed farming ideas without forbidding novel combinations."""
    state = _ensure(state)
    agro = state['agro_reasoning']
    family = agro['families'].get(strategy_family(params), {})
    fail = int(family.get('fail', 0) or 0)
    win = int(family.get('win', 0) or 0)
    penalty = max(0.0, (fail - win) / max(2.0, fail + win))

    for reason, count in dominant_failures(state, 8):
        if int(count) < 2:
            continue
        values = agro['reason_values'].get(reason, {})
        matched = 0
        considered = 0
        for key, value in params.items():
            if isinstance(value, dict) or key not in values:
                continue
            considered += 1
            if int(values[key].get(_bucket(value), 0) or 0) >= 2:
                matched += 1
        if considered and matched / considered >= .35:
            penalty += min(.8, .08 * int(count))
    return min(4.0, penalty)


def agro_quality_score(evaluation, params):
    """Small domain prior: productive capital + price discipline, never a substitute for money."""
    m = evaluation.get('metrics', {})
    util = float(m.get('mean_full_farm_peak_productive_utilization', 0.0) or 0.0)
    animals = float(m.get('mean_peak_animals', 0.0) or 0.0)
    waste = float(m.get('mean_terminal_unsold_units', 0.0) or 0.0)
    score = 18.0 * min(1.0, max(0.0, util)) + 2.0 * min(10.0, animals) - 1.2 * waste

    # Dynamic market lesson: premium gluts are expensive; smaller batches and demand/ROI modes
    # make production and price realization cooperate instead of maximizing volume blindly.
    batch = int(params.get('sell_batch', 6) or 6)
    premium_herd = int(params.get('cow_max', 0) or 0) + int(params.get('sheep_max', 0) or 0)
    if premium_herd >= 8:
        score += 7.0 if batch <= 5 else (-8.0 if batch >= 8 else 0.0)
    if params.get('crop_mode') in ('roi', 'demand'):
        score += 5.0
    if premium_herd >= 8 and int(params.get('feed_carry', 0) or 0) >= 6:
        score += 5.0
    if int(params.get('land_target_quadrants', 4) or 4) == 4 and int(params.get('target_hands', 0) or 0) >= 12:
        score -= 8.0
    return score


def recovery_patches(state, accepted=None, limit=8):
    """Translate repeated failures into concrete new farming hypotheses for the next pool."""
    state = _ensure(state)
    accepted = dict(accepted or {})
    reasons = {name for name, count in dominant_failures(state, 10) if int(count) >= 2}
    patches = []

    def add(patch):
        q = dict(accepted)
        q.update(patch)
        if q not in patches:
            patches.append(q)

    if 'fourth_quadrant_overreach' in reasons:
        add({'land_target_quadrants': 3, 'target_hands': min(10, int(accepted.get('target_hands', 10) or 10)), 'land_buffer': max(120, int(accepted.get('land_buffer', 120) or 120))})
    if 'labor_overhead' in reasons or 'routing_overhead' in reasons:
        add({'target_hands': 9, 'distance_cost': max(7.0, float(accepted.get('distance_cost', 7.0) or 7.0)), 'land_target_quadrants': 3})
    if 'herd_feed_pressure' in reasons or 'livestock_without_crop_support' in reasons:
        add({'crop_mode': 'grains', 'feed_carry': 8, 'seed_scale': 1.7, 'sell_batch': 5, 'fertilizer_mode': 'adaptive'})
        add({'crop_mode': 'roi', 'feed_carry': 8, 'seed_scale': 1.45, 'animal_roi_floor': max(.10, float(accepted.get('animal_roi_floor', .10) or .10))})
    if 'premium_glut_dumping' in reasons or 'volume_over_value' in reasons:
        add({'crop_mode': 'demand', 'sell_batch': 4, 'animal_roi_floor': max(.20, float(accepted.get('animal_roi_floor', .20) or .20)), 'fertilizer_reserve': 1})
        add({'crop_mode': 'roi', 'sell_batch': 5, 'goose_max': 0, 'feed_carry': 8})
    if 'underutilized_land' in reasons:
        add({'fill_target': .88, 'fill_priority': 105.0, 'distance_cost': 6.0, 'target_hands': max(10, min(11, int(accepted.get('target_hands', 10) or 10)))})
    if 'terminal_inventory' in reasons:
        add({'drop_at': 6, 'sell_batch': 4, 'crop_mode': 'demand'})
    if 'crop_only_income_ceiling' in reasons:
        add({'herd_mode': 'cow_sheep', 'cow_max': 9, 'sheep_max': 4, 'goose_max': 0, 'feed_carry': 8, 'sell_batch': 4, 'land_target_quadrants': 3})
    if 'herd_capital_not_converted' in reasons or 'idle_structure_capital' in reasons:
        add({'livestock_start_day': 0, 'livestock_cash_buffer': 500, 'animal_roi_floor': .10, 'target_hands': 10, 'land_target_quadrants': 3})

    return patches[:max(0, int(limit))]


def summary(state):
    state = _ensure(state)
    agro = state['agro_reasoning']
    return {
        'events': int(agro.get('events', 0) or 0),
        'loss_events': int(agro.get('loss_events', 0) or 0),
        'win_events': int(agro.get('win_events', 0) or 0),
        'dominant_failures': dominant_failures(state, 8),
        'strategy_families': dict(agro.get('families', {})),
    }
