"""Persistent, deterministic learning for the Kaggriculture rank lane.

The learner consumes only our own local evaluation telemetry. It never reads hidden Kaggle
state and never writes source/champion files. The workflow serializes the single learning-
state writer, while this module writes state atomically so interrupted runs cannot leave a
half-written memory file.

V5.5 extends the original win/loss learner with four conservative capabilities:
1) opponent-family-conditioned parameter evidence;
2) an elite archive that survives later rounds;
3) stagnation/regression detection;
4) an adaptive search controller that increases exploration only when evidence warrants it.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

# Keep version 1 so existing V5.4 cache files migrate in-place instead of being discarded.
STATE_VERSION = 1
IGNORE_KEYS = {'route', 'market', 'endgame'}
MAX_ROUND_HISTORY = 24
MAX_CHAMPIONS = 8


def _blank_control():
    return {
        'rounds': 0,
        'best_score': None,
        'stagnation': 0,
        'regressions': 0,
        'last_score': None,
        'last_improved': False,
    }


def blank_state():
    return {
        'version': STATE_VERSION,
        'matches': 0,
        'wins': 0,
        'losses': 0,
        'ties': 0,
        'invalid': 0,
        'values': {},
        'conditional_values': {},
        'families': {},
        'seats': {},
        'signals': {},
        'round_history': [],
        'champions': [],
        'control': _blank_control(),
        'updated_at': None,
    }


def _normalize_state(raw):
    out = blank_state()
    if isinstance(raw, dict):
        out.update(raw)
    for key in ('values', 'conditional_values', 'families', 'seats', 'signals'):
        if not isinstance(out.get(key), dict):
            out[key] = {}
    for key in ('round_history', 'champions'):
        if not isinstance(out.get(key), list):
            out[key] = []
    control = _blank_control()
    if isinstance(out.get('control'), dict):
        control.update(out['control'])
    out['control'] = control
    out['version'] = STATE_VERSION
    return out


def load_state(path=None):
    if not path:
        return blank_state()
    p = Path(path)
    if not p.exists():
        return blank_state()
    try:
        raw = json.loads(p.read_text())
    except (OSError, ValueError, TypeError):
        return blank_state()
    if not isinstance(raw, dict) or raw.get('version') != STATE_VERSION:
        return blank_state()
    return _normalize_state(raw)


def save_state(path, state):
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state = _normalize_state(dict(state))
    state['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(p)


def _bucket(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _update_stat(table, key, reward):
    s = table.setdefault(str(key), {'n': 0, 'sum': 0.0, 'sum_sq': 0.0, 'wins': 0, 'losses': 0})
    # Old cache entries did not contain sum_sq. Migrate lazily without resetting evidence.
    s.setdefault('sum_sq', 0.0)
    s.setdefault('wins', 0)
    s.setdefault('losses', 0)
    s['n'] = int(s.get('n', 0)) + 1
    s['sum'] = float(s.get('sum', 0.0)) + float(reward)
    s['sum_sq'] = float(s.get('sum_sq', 0.0)) + float(reward) ** 2
    s['wins'] += int(reward > 0)
    s['losses'] += int(reward < 0)


def _mean(stat):
    n = max(1, int((stat or {}).get('n', 0) or 0))
    return float((stat or {}).get('sum', 0.0) or 0.0) / n


def _reward(row):
    if not row.get('valid'):
        return -2.0
    margin = float(row.get('margin', 0.0) or 0.0)
    r = math.tanh(margin / 5500.0)
    eff = row.get('efficiency') or {}
    actions = max(1, int(eff.get('actions', 0) or 0))
    r -= min(.50, 5.0 * int(eff.get('noops', 0) or 0) / actions)
    r -= min(.25, float(row.get('terminal_unsold_units', 0) or 0) / 100.0)
    r += min(.12, float(row.get('peak_animals', 0) or 0) / 100.0)
    return max(-2.0, min(2.0, r))


def observe_evaluation(state, params, evaluation, label=''):
    """Consume every game row so wins, losses, ties and invalid games all alter learning."""
    state = _normalize_state(state)
    for row in evaluation.get('rows', []):
        reward = _reward(row)
        family = str(row.get('opponent', 'unknown'))
        state['matches'] += 1
        if not row.get('valid'):
            state['invalid'] += 1
        elif float(row.get('margin', 0) or 0) > 0:
            state['wins'] += 1
        elif float(row.get('margin', 0) or 0) < 0:
            state['losses'] += 1
        else:
            state['ties'] += 1
        _update_stat(state['families'], family, reward)
        _update_stat(state['seats'], row.get('seat', 'unknown'), reward)
        family_values = state['conditional_values'].setdefault(family, {})
        for key, value in params.items():
            if key in IGNORE_KEYS or isinstance(value, dict):
                continue
            bucket = _bucket(value)
            _update_stat(state['values'].setdefault(key, {}), bucket, reward)
            _update_stat(family_values.setdefault(key, {}), bucket, reward)
        if not row.get('valid'):
            _update_stat(state['signals'], 'invalid', -1)
        if int((row.get('efficiency') or {}).get('noops', 0) or 0) > 0:
            _update_stat(state['signals'], 'unit_noop', -1)
        if float(row.get('terminal_unsold_units', 0) or 0) > 8:
            _update_stat(state['signals'], 'terminal_inventory', -1)
        if float(row.get('margin', 0) or 0) < -5000:
            _update_stat(state['signals'], 'catastrophic_loss', -1)
    state['last_label'] = label
    return state


def weak_families(state, limit=2, min_samples=2):
    ranked = []
    for name, stat in state.get('families', {}).items():
        n = int((stat or {}).get('n', 0) or 0)
        if n >= min_samples:
            ranked.append((_mean(stat), n, str(name)))
    ranked.sort(key=lambda x: (x[0], -x[1], x[2]))
    return [name for _, _, name in ranked[:max(0, int(limit))]]


def value_score(state, key, value, focus_families=None):
    bucket = _bucket(value)
    global_stat = state.get('values', {}).get(key, {}).get(bucket)
    if not global_stat or not global_stat.get('n'):
        global_score = 0.06
    else:
        n = int(global_stat['n'])
        global_score = _mean(global_stat) + min(.12, .22 / math.sqrt(n))

    family_scores = []
    for family in focus_families or ():
        stat = state.get('conditional_values', {}).get(str(family), {}).get(key, {}).get(bucket)
        if stat and int(stat.get('n', 0) or 0) > 0:
            n = int(stat['n'])
            family_scores.append(_mean(stat) + min(.10, .16 / math.sqrt(n)))
    if family_scores:
        return .62 * global_score + .38 * (sum(family_scores) / len(family_scores))
    return global_score


def best_learned_patch(state, choices, min_samples=4, focus_families=None):
    patch = {}
    for key, vals in choices.items():
        ranked = []
        table = state.get('values', {}).get(key, {})
        for value in vals:
            stat = table.get(_bucket(value))
            if stat and int(stat.get('n', 0)) >= min_samples:
                ranked.append((value_score(state, key, value, focus_families), int(stat['n']), value))
        if ranked:
            ranked.sort(key=lambda x: (x[0], x[1], repr(x[2])), reverse=True)
            if ranked[0][0] > 0:
                patch[key] = ranked[0][2]
    return patch


def mutation_key(state, params, choices, rng, focus_families=None, exploration=.18):
    keys = [k for k in choices if k in params and len(set(map(repr, choices[k]))) > 1]
    weights = []
    for key in keys:
        current = value_score(state, key, params[key], focus_families)
        # Weak current values are changed more often. Exploration prevents premature lock-in.
        weights.append(max(.04, .42 - current) + max(0.0, float(exploration)) * .20)
    return rng.choices(keys, weights=weights, k=1)[0]


def mutation_value(state, key, current, choices, rng, focus_families=None, exploration=.18):
    vals = [v for v in choices[key] if v != current]
    if not vals:
        return current
    scores = [value_score(state, key, v, focus_families) for v in vals]
    floor = min(scores)
    epsilon = max(.02, min(.30, .04 + float(exploration) * .20))
    weights = [max(epsilon, score - floor + epsilon) for score in scores]
    return rng.choices(vals, weights=weights, k=1)[0]


def learned_variants(elites, state, choices, validate, rng, target, focus_families=None,
                     exploration=.18, mutation_steps=1):
    """Preserve elites and fill the pool with evidence-guided multi-step mutations."""
    out = []
    for p in elites:
        q = validate(dict(p))
        if q not in out:
            out.append(q)
        if len(out) >= target:
            return out[:target]
    attempts = 0
    max_steps = max(1, min(4, int(mutation_steps)))
    while len(out) < target and attempts < target * 60:
        attempts += 1
        q = dict(rng.choice(elites))
        steps = 1 + rng.randrange(max_steps)
        # During high exploration, occasionally add one more move without exceeding 4.
        if rng.random() < max(0.0, min(.50, float(exploration))) and steps < 4:
            steps += 1
        for _ in range(steps):
            k = mutation_key(state, q, choices, rng, focus_families, exploration)
            q[k] = mutation_value(state, k, q[k], choices, rng, focus_families, exploration)
        try:
            q = validate(q)
        except (ValueError, TypeError):
            continue
        if q not in out:
            out.append(q)
    return out[:target]


def _metric(metrics, key, default=0.0):
    try:
        return float((metrics or {}).get(key, default) or default)
    except (TypeError, ValueError):
        return float(default)


def round_score(duel, holdout, final):
    """Stable potential score for comparing local rounds; never replaces promotion gates."""
    win = (_metric(duel, 'win_rate') + _metric(holdout, 'win_rate') + _metric(final, 'win_rate')) / 3.0
    margin = (.20 * _metric(duel, 'mean_margin') + .35 * _metric(holdout, 'mean_margin') +
              .45 * _metric(final, 'mean_margin'))
    tail = .5 * _metric(holdout, 'worst_margin') + .5 * _metric(final, 'worst_margin')
    waste = .5 * _metric(holdout, 'mean_terminal_unsold_units') + .5 * _metric(final, 'mean_terminal_unsold_units')
    catastrophic = max(_metric(holdout, 'catastrophic_rate'), _metric(final, 'catastrophic_rate'))
    return margin + 6000.0 * win + .08 * tail - 45.0 * waste - 12000.0 * catastrophic


def champion_params(state, limit=4):
    out = []
    for item in state.get('champions', [])[:max(0, int(limit))]:
        params = item.get('params') if isinstance(item, dict) else None
        if isinstance(params, dict) and params not in out:
            out.append(dict(params))
    return out


def record_round(state, params, duel, holdout, final, promotion=None, label=''):
    """Record round-level progress and retain a bounded elite archive."""
    state = _normalize_state(state)
    score = float(round_score(duel, holdout, final))
    control = state['control']
    previous_best = control.get('best_score')
    improved = previous_best is None or score > float(previous_best) + max(75.0, abs(float(previous_best)) * .002)
    regressed = control.get('last_score') is not None and score < float(control['last_score']) - 250.0
    control['rounds'] = int(control.get('rounds', 0) or 0) + 1
    control['last_score'] = score
    control['last_improved'] = bool(improved)
    if improved:
        control['best_score'] = score
        control['stagnation'] = 0
    else:
        control['stagnation'] = int(control.get('stagnation', 0) or 0) + 1
    if regressed:
        control['regressions'] = int(control.get('regressions', 0) or 0) + 1

    entry = {
        'label': str(label),
        'score': score,
        'improved': bool(improved),
        'promotion': bool((promotion or {}).get('pass_gate', False)),
        'params': dict(params),
        'duel_win_rate': _metric(duel, 'win_rate'),
        'holdout_win_rate': _metric(holdout, 'win_rate'),
        'final_win_rate': _metric(final, 'win_rate'),
        'final_mean_margin': _metric(final, 'mean_margin'),
    }
    state['round_history'].append(entry)
    state['round_history'] = state['round_history'][-MAX_ROUND_HISTORY:]

    archive = [x for x in state.get('champions', []) if isinstance(x, dict)]
    sig = _bucket(params)
    archive = [x for x in archive if _bucket(x.get('params', {})) != sig]
    archive.append({'score': score, 'params': dict(params), 'label': str(label), 'promotion': entry['promotion']})
    archive.sort(key=lambda x: (float(x.get('score', -1e30)), _bucket(x.get('params', {}))), reverse=True)
    state['champions'] = archive[:MAX_CHAMPIONS]
    return state


def adaptive_plan(state, requested_candidates=24):
    """Choose next search breadth/depth from evidence, not from a fixed forever setting."""
    state = _normalize_state(state)
    requested = max(8, min(64, int(requested_candidates or 24)))
    control = state['control']
    rounds = int(control.get('rounds', 0) or 0)
    stagnation = int(control.get('stagnation', 0) or 0)
    regressions = int(control.get('regressions', 0) or 0)
    deep_round = rounds > 0 and (rounds + 1) % 5 == 0

    candidates = requested
    exploration = .16
    mutation_steps = 1
    mode = 'exploit'
    if stagnation >= 4:
        candidates = max(candidates, 56)
        exploration = .42
        mutation_steps = 4
        mode = 'escape-stagnation'
    elif stagnation >= 2:
        candidates = max(candidates, 40)
        exploration = .32
        mutation_steps = 3
        mode = 'broaden'
    elif regressions and not control.get('last_improved', False):
        candidates = max(candidates, 32)
        exploration = .26
        mutation_steps = 2
        mode = 'recover'
    if deep_round:
        candidates = max(candidates, 48)
        exploration = max(exploration, .34)
        mutation_steps = max(mutation_steps, 3)
        mode = 'periodic-deep'

    return {
        'candidate_count': max(8, min(64, int(candidates))),
        'exploration': round(float(exploration), 3),
        'mutation_steps': int(mutation_steps),
        'focus_families': weak_families(state, limit=2, min_samples=2),
        'mode': mode,
        'round_index': rounds + 1,
        'stagnation': stagnation,
        'best_score': control.get('best_score'),
    }
