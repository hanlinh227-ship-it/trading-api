#!/usr/bin/env python3
import json
import statistics
from collections import defaultdict

PATH = 'data/blind_backtest_v24_validation.json'
TARGETS = ['BLIND_JUN30', 'BLIND_JUN27']


def summary(rows):
    resolved = [r for r in rows if r.get('outcome', {}).get('result') in ('TP', 'SL')]
    wins = [r for r in resolved if r['outcome']['result'] == 'TP']
    losses = [r for r in resolved if r['outcome']['result'] == 'SL']
    total = sum(r['plannedRR'] if r['outcome']['result'] == 'TP' else -1 for r in resolved)
    return {
        'trades': len(rows),
        'resolved': len(resolved),
        'wins': len(wins),
        'losses': len(losses),
        'unresolved': len(rows) - len(resolved),
        'wr': round(100 * len(wins) / len(resolved), 2) if resolved else None,
        'expectancyR': round(total / len(resolved), 3) if resolved else None,
    }


def flow_relation(r):
    f = r.get('flow') or {}
    if not f.get('available'):
        return 'unavailable'
    ma = r.get('macroScore') or 0.0
    mi = r.get('microScore') or 0.0
    if abs(mi) < 1e-12:
        return 'neutral'
    return 'agree' if ma * mi > 0 else 'conflict'


def score_bin(r):
    x = abs(r.get('score') or 0.0)
    if x < 1: return '<1'
    if x < 2: return '1-2'
    if x < 3: return '2-3'
    if x < 4: return '3-4'
    return '>=4'


def raw_side(r):
    return 'BUY' if (r.get('macroScore') or 0.0) + (r.get('microScore') or 0.0) >= 0 else 'SELL'


def grouped(rows, key):
    d = defaultdict(list)
    for r in rows:
        d[key(r)].append(r)
    return {str(k): summary(v) for k, v in sorted(d.items(), key=lambda kv: str(kv[0]))}


def med(rows, field):
    xs = [r.get(field) for r in rows if isinstance(r.get(field), (int, float))]
    return round(statistics.median(xs), 3) if xs else None


def diagnose(sample):
    rows = sample['tests']
    resolved = [r for r in rows if r.get('outcome', {}).get('result') in ('TP', 'SL')]
    wins = [r for r in resolved if r['outcome']['result'] == 'TP']
    losses = [r for r in resolved if r['outcome']['result'] == 'SL']

    changed = [r for r in rows if raw_side(r) != r.get('decision')]
    unchanged = [r for r in rows if raw_side(r) == r.get('decision')]

    return {
        'market': {
            'cutoff': sample['cutoff'],
            'marketRegime': sample['marketRegime'],
            'priceBreadth': sample['priceBreadth'],
            'flowBreadth': sample['flowBreadth'],
            'flowMedian': sample['flowMedian'],
            'flowCoverage': sample['flowCoverage'],
        },
        'overall': summary(rows),
        'byDecision': grouped(rows, lambda r: r.get('decision', 'NONE')),
        'byProfile': grouped(rows, lambda r: (r.get('model') or {}).get('profile', 'unknown')),
        'byInternalRegime': grouped(rows, lambda r: (r.get('model') or {}).get('regime', 'unknown')),
        'byFlowRelation': grouped(rows, flow_relation),
        'byAbsScore': grouped(rows, score_bin),
        'regimeGuardChangedSide': summary(changed),
        'regimeGuardKeptRawSide': summary(unchanged),
        'guardChangedCount': len(changed),
        'winnerMedians': {
            'macro': med(wins, 'macroScore'),
            'micro': med(wins, 'microScore'),
            'score': med(wins, 'score'),
            'ofi': round(statistics.median([r['flow']['ofi'] for r in wins if (r.get('flow') or {}).get('available')]), 3) if any((r.get('flow') or {}).get('available') for r in wins) else None,
        },
        'loserMedians': {
            'macro': med(losses, 'macroScore'),
            'micro': med(losses, 'microScore'),
            'score': med(losses, 'score'),
            'ofi': round(statistics.median([r['flow']['ofi'] for r in losses if (r.get('flow') or {}).get('available')]), 3) if any((r.get('flow') or {}).get('available') for r in losses) else None,
        },
        'lossConcentration': {
            'buyLosses': sum(1 for r in losses if r.get('decision') == 'BUY'),
            'sellLosses': sum(1 for r in losses if r.get('decision') == 'SELL'),
            'flowAgreeLosses': sum(1 for r in losses if flow_relation(r) == 'agree'),
            'flowConflictLosses': sum(1 for r in losses if flow_relation(r) == 'conflict'),
            'flowUnavailableLosses': sum(1 for r in losses if flow_relation(r) == 'unavailable'),
        },
    }


def main():
    with open(PATH) as f:
        payload = json.load(f)
    out = {name: diagnose(payload['samples'][name]) for name in TARGETS}
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
