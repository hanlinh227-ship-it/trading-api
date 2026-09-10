"""Persistent, deterministic learning from local Kaggriculture match outcomes.

This module learns only from our own local evaluation telemetry.  It never reads hidden
Kaggle state and never writes source/champion files, so concurrent research cannot corrupt
Git history.  The workflow serializes the single learning-state writer.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

STATE_VERSION = 1
IGNORE_KEYS = {'route', 'market', 'endgame'}


def blank_state():
    return {
        'version': STATE_VERSION,
        'matches': 0,
        'wins': 0,
        'losses': 0,
        'ties': 0,
        'invalid': 0,
        'values': {},
        'families': {},
        'seats': {},
        'signals': {},
        'updated_at': None,
    }


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
    out = blank_state()
    out.update(raw)
    for k in ('values', 'families', 'seats', 'signals'):
        if not isinstance(out.get(k), dict):
            out[k] = {}
    return out


def save_state(path, state):
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(p)


def _bucket(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _update_stat(table, key, reward):
    s = table.setdefault(str(key), {'n': 0, 'sum': 0.0, 'wins': 0, 'losses': 0})
    s['n'] += 1
    s['sum'] += float(reward)
    s['wins'] += int(reward > 0)
    s['losses'] += int(reward < 0)


def _reward(row):
    if not row.get('valid'):
        return -2.0
    margin = float(row.get('margin', 0.0) or 0.0)
    r = math.tanh(margin / 5500.0)
    eff = row.get('efficiency') or {}
    actions = max(1, int(eff.get('actions', 0) or 0))
    r -= min(.50, 5.0 * int(eff.get('noops', 0) or 0) / actions)
    r -= min(.25, float(row.get('terminal_unsold_units', 0) or 0) / 100.0)
    # A tiny economic credit rewards useful production without forcing four quadrants.
    r += min(.12, float(row.get('peak_animals', 0) or 0) / 100.0)
    return max(-2.0, min(2.0, r))


def observe_evaluation(state, params, evaluation, label=''):
    """Consume every game row, so both wins and losses alter the next search."""
    for row in evaluation.get('rows', []):
        reward = _reward(row)
        state['matches'] += 1
        if not row.get('valid'):
            state['invalid'] += 1
        elif float(row.get('margin', 0) or 0) > 0:
            state['wins'] += 1
        elif float(row.get('margin', 0) or 0) < 0:
            state['losses'] += 1
        else:
            state['ties'] += 1
        _update_stat(state['families'], row.get('opponent', 'unknown'), reward)
        _update_stat(state['seats'], row.get('seat', 'unknown'), reward)
        for key, value in params.items():
            if key in IGNORE_KEYS or isinstance(value, dict):
                continue
            table = state['values'].setdefault(key, {})
            _update_stat(table, _bucket(value), reward)
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


def value_score(state, key, value):
    s = state.get('values', {}).get(key, {}).get(_bucket(value))
    if not s or not s.get('n'):
        # Unknown values retain exploration value instead of being permanently excluded.
        return 0.06
    n = int(s['n'])
    mean = float(s['sum']) / n
    explore = min(.12, .22 / math.sqrt(n))
    return mean + explore


def best_learned_patch(state, choices, min_samples=4):
    patch = {}
    for key, vals in choices.items():
        table = state.get('values', {}).get(key, {})
        ranked = []
        for value in vals:
            s = table.get(_bucket(value))
            if s and int(s.get('n', 0)) >= min_samples:
                ranked.append((float(s['sum']) / int(s['n']), int(s['n']), value))
        if ranked:
            ranked.sort(key=lambda x: (x[0], x[1], repr(x[2])), reverse=True)
            if ranked[0][0] > 0:
                patch[key] = ranked[0][2]
    return patch


def mutation_key(state, params, choices, rng):
    keys = [k for k in choices if k in params and len(set(map(repr, choices[k]))) > 1]
    weights = []
    for key in keys:
        current = value_score(state, key, params[key])
        # Poor current values are changed more often; uncertain keys still get exploration.
        weights.append(max(.05, .40 - current))
    return rng.choices(keys, weights=weights, k=1)[0]


def mutation_value(state, key, current, choices, rng):
    vals = [v for v in choices[key] if v != current]
    if not vals:
        return current
    scores = [value_score(state, key, v) for v in vals]
    floor = min(scores)
    weights = [max(.02, s - floor + .08) for s in scores]
    return rng.choices(vals, weights=weights, k=1)[0]


def learned_variants(elites, state, choices, validate, rng, target):
    """Keep elites and fill remaining slots with outcome-guided one/two-step mutations."""
    out = []
    for p in elites:
        q = validate(dict(p))
        if q not in out:
            out.append(q)
        if len(out) >= target:
            return out[:target]
    attempts = 0
    while len(out) < target and attempts < target * 40:
        attempts += 1
        q = dict(rng.choice(elites))
        for _ in range(1 + int(rng.random() < .25)):
            k = mutation_key(state, q, choices, rng)
            q[k] = mutation_value(state, k, q[k], choices, rng)
        try:
            q = validate(q)
        except (ValueError, TypeError):
            continue
        if q not in out:
            out.append(q)
    return out[:target]
