"""Domain reasoning for crop/livestock failures and recovery.

Every local episode becomes agronomic/economic evidence instead of a binary win/loss.  The
learner decomposes capital failures into land, labor, crop mix, herd/feed, utilization, sale
price capture and inventory causes, then converts repeated causes into new hypotheses.

Only our own current-engine telemetry and public game mechanics/meta priors are consumed.  No
hidden Kaggle state or copied opponent action tape is used.  Public top patterns are priors;
our personal success/failure memory and monotonic capital gate always have priority.
"""
from __future__ import annotations

import json

# Public high-Elo priors observed in replay/meta discussion.  They are broad structural priors,
# not exact 720-turn scripts.  Search can and should reject them when our own evidence is better.
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


def _sum_map(d):
    return sum(float(v or 0) for v in (d or {}).values())


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
    eco = row.get('economy') or {}

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

    # Rich V5.7 economy telemetry: diagnose *why* nominally productive farms still lose money.
    if eco:
        min_money = eco.get('min_money')
        if min_money is not None and float(min_money) < 250 and margin < 0:
            reasons.append('capital_starvation')
        land_buys = float(eco.get('planned_buy_land', 0) or 0)
        hires = float(eco.get('planned_hires', 0) or 0)
        if land_buys >= 3 and margin < 0 and (min_money is None or float(min_money) < 700):
            reasons.append('expansion_cash_drag')
        if hires >= 12 and margin < 0:
            reasons.append('hiring_cash_drag')

        sold_units = _sum_map(eco.get('planned_sell_units'))
        capture = float(eco.get('planned_sell_capture_ratio', 0.0) or 0.0)
        if sold_units >= 12 and capture > 0 and capture < .74 and margin < 0:
            reasons.append('poor_price_capture')

        buy_wheat = float(eco.get('planned_buy_wheat', 0) or 0)
        animal_exposure = _sum_map(eco.get('animal_exposure'))
        if buy_wheat >= 8 and animal_exposure >= 4 and margin < 0:
            reasons.append('feed_market_dependency')

        crop_exp = eco.get('crop_exposure') or {}
        animal_exp = eco.get('animal_exposure') or {}
        premium_exposure = float(crop_exp.get('STRAWBERRY', 0) or 0) + float(crop_exp.get('MELON', 0) or 0) + float(animal_exp.get('COW', 0) or 0) + float(animal_exp.get('SHEEP', 0) or 0)
        if premium_exposure >= 7 and sold_units >= 12 and capture > 0 and capture < .82 and margin < 0:
            reasons.append('premium_supply_price_mismatch')

        checkpoints = eco.get('money_checkpoints') or {}
        early = [float(checkpoints.get(str(d), 0) or 0) for d in (5, 10, 15) if checkpoints.get(str(d)) is not None]
        late = [float(checkpoints.get(str(d), 0) or 0) for d in (20, 25, 29) if checkpoints.get(str(d)) is not None]
        if early and late and max(early) > 0 and max(late) <= max(early) * 1.10 and margin < 0:
            reasons.append('capital_not_compounding')

    if margin < -5000:
        reasons.append('catastrophic_economics')
    return list(dict.fromkeys(reasons))


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
    """Softly avoid repeatedly failed farming ideas without globally banning exploration."""
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
        matched = 0; considered = 0
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
    """Reward productive output *and* strong price realization; money gate remains authoritative."""
    m = evaluation.get('metrics', {})
    util = float(m.get('mean_peak_productive_utilization', m.get('mean_full_farm_peak_productive_utilization', 0.0)) or 0.0)
    animals = float(m.get('mean_peak_animals', 0.0) or 0.0)
    waste = float(m.get('mean_terminal_unsold_units', 0.0) or 0.0)
    capture = float(m.get('mean_planned_sell_capture_ratio', 1.0) or 1.0)
    scarcity = float(m.get('mean_planned_sell_scarcity', 0.0) or 0.0)
    score = 24.0 * min(1.0, max(0.0, util)) + 1.5 * min(12.0, animals) - 1.2 * waste
    # Price and production are joint objectives: high output sold at poor quotes is not progress.
    score += 18.0 * max(-.5, min(.6, capture - .75))
    score += min(8.0, max(0.0, scarcity) / 80.0)

    batch = int(params.get('sell_batch', 6) or 6)
    premium_herd = int(params.get('cow_max', 0) or 0) + int(params.get('sheep_max', 0) or 0)
    if premium_herd >= 8:
        score += 7.0 if batch <= 5 else (-8.0 if batch >= 8 else 0.0)
    if params.get('crop_mode') in ('roi', 'demand', 'grains'):
        score += 5.0
    if premium_herd >= 8 and int(params.get('feed_carry', 0) or 0) >= 6:
        score += 5.0
    if int(params.get('land_target_quadrants', 4) or 4) == 4 and int(params.get('target_hands', 0) or 0) >= 12:
        score -= 8.0
    return score


def recovery_patches(state, accepted=None, limit=10):
    """Translate repeated mistakes into materially different crop/livestock hypotheses."""
    state = _ensure(state)
    accepted = dict(accepted or {})
    reasons = {name for name, count in dominant_failures(state, 16) if int(count) >= 2}
    patches = []

    def add(patch):
        q = dict(accepted); q.update(patch)
        if q not in patches:
            patches.append(q)

    if 'fourth_quadrant_overreach' in reasons or 'expansion_cash_drag' in reasons:
        add({'land_target_quadrants': 3, 'target_hands': min(10, int(accepted.get('target_hands', 10) or 10)), 'land_buffer': 260, 'livestock_cash_buffer': max(650, int(accepted.get('livestock_cash_buffer', 650) or 650))})
    if 'labor_overhead' in reasons or 'routing_overhead' in reasons or 'hiring_cash_drag' in reasons:
        add({'target_hands': 9, 'distance_cost': max(7.0, float(accepted.get('distance_cost', 7.0) or 7.0)), 'land_target_quadrants': 3})
    if 'herd_feed_pressure' in reasons or 'livestock_without_crop_support' in reasons or 'feed_market_dependency' in reasons:
        add({'crop_mode': 'grains', 'feed_carry': 8, 'seed_scale': 1.7, 'sell_batch': 5, 'fertilizer_mode': 'adaptive'})
        add({'crop_mode': 'roi', 'feed_carry': 8, 'seed_scale': 1.45, 'cow_max': min(9, int(accepted.get('cow_max', 9) or 9)), 'sheep_max': min(4, int(accepted.get('sheep_max', 4) or 4)), 'animal_roi_floor': max(.10, float(accepted.get('animal_roi_floor', .10) or .10))})
    if 'premium_glut_dumping' in reasons or 'volume_over_value' in reasons or 'poor_price_capture' in reasons or 'premium_supply_price_mismatch' in reasons:
        add({'crop_mode': 'demand', 'sell_batch': 4, 'animal_roi_floor': max(.20, float(accepted.get('animal_roi_floor', .20) or .20)), 'fertilizer_reserve': 1, 'goose_max': 0})
        add({'crop_mode': 'roi', 'sell_batch': 5, 'goose_max': 0, 'feed_carry': 8, 'sheep_max': min(4, int(accepted.get('sheep_max', 4) or 4))})
    if 'underutilized_land' in reasons:
        add({'fill_target': .88, 'fill_priority': 105.0, 'distance_cost': 6.0, 'target_hands': max(10, min(11, int(accepted.get('target_hands', 10) or 10)))})
    if 'terminal_inventory' in reasons:
        add({'drop_at': 6, 'sell_batch': 4, 'crop_mode': 'demand'})
    if 'crop_only_income_ceiling' in reasons:
        add({'herd_mode': 'cow_sheep', 'cow_max': 9, 'sheep_max': 4, 'goose_max': 0, 'feed_carry': 8, 'sell_batch': 4, 'land_target_quadrants': 3})
    if 'herd_capital_not_converted' in reasons or 'idle_structure_capital' in reasons:
        add({'livestock_start_day': 0, 'livestock_cash_buffer': 500, 'animal_roi_floor': .10, 'target_hands': 10, 'land_target_quadrants': 3})
    if 'capital_starvation' in reasons or 'capital_not_compounding' in reasons:
        add({'land_target_quadrants': 3, 'land_buffer': 260, 'livestock_cash_buffer': 650, 'crop_mode': 'roi', 'sell_batch': 4, 'target_hands': 10})
        add({'land_target_quadrants': 3, 'crop_mode': 'demand', 'cow_max': 9, 'sheep_max': 4, 'feed_carry': 8, 'sell_batch': 4, 'target_hands': 9})
    return patches[:max(0, int(limit))]


def summary(state):
    state = _ensure(state)
    agro = state['agro_reasoning']
    return {
        'events': int(agro.get('events', 0) or 0),
        'loss_events': int(agro.get('loss_events', 0) or 0),
        'win_events': int(agro.get('win_events', 0) or 0),
        'dominant_failures': dominant_failures(state, 10),
        'strategy_families': dict(agro.get('families', {})),
    }
