#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone

import blind_backtest_crypto_v24 as v24

# Locked V24-Core validation batch.
# These June cutoffs were selected before outcomes were inspected and are outside the
# August/July development/blind dates documented in the retained research lineage.
# IMPORTANT: this file does not alter V24 scoring, regime thresholds, SL logic or RR logic.
CUTOFFS = [
    ('BLIND_JUN30', '2026-06-30T12:00:00Z'),
    ('BLIND_JUN27', '2026-06-27T12:00:00Z'),
    ('BLIND_JUN24', '2026-06-24T12:00:00Z'),
    ('BLIND_JUN21', '2026-06-21T12:00:00Z'),
    ('BLIND_JUN18', '2026-06-18T12:00:00Z'),
]


def summarize_group(rows):
    resolved = [r for r in rows if r.get('outcome', {}).get('result') in ('TP', 'SL')]
    wins = [r for r in resolved if r['outcome']['result'] == 'TP']
    losses = [r for r in resolved if r['outcome']['result'] == 'SL']
    total_r = sum(r['plannedRR'] if r['outcome']['result'] == 'TP' else -1 for r in resolved)
    return {
        'trades': len(rows),
        'resolved': len(resolved),
        'wins': len(wins),
        'losses': len(losses),
        'unresolved': len(rows) - len(resolved),
        'winRateResolved': round(100 * len(wins) / len(resolved), 2) if resolved else None,
        'avgPlannedRR': round(sum(r['plannedRR'] for r in resolved) / len(resolved), 3) if resolved else None,
        'expectancyR': round(total_r / len(resolved), 3) if resolved else None,
    }


def flow_relation(row):
    flow = row.get('flow') or {}
    if not flow.get('available'):
        return 'unavailable'
    macro = row.get('macroScore') or 0.0
    micro = row.get('microScore') or 0.0
    if abs(micro) < 1e-12:
        return 'neutral'
    return 'agree' if macro * micro > 0 else 'conflict' if macro * micro < 0 else 'neutral'


def main():
    samples = {label: v24.run(label, cutoff) for label, cutoff in CUTOFFS}
    all_rows = [row for sample in samples.values() for row in sample['tests']]

    by_profile = defaultdict(list)
    by_flow_relation = defaultdict(list)
    by_regime = defaultdict(list)
    for row in all_rows:
        profile = (row.get('model') or {}).get('profile', 'unknown')
        by_profile[profile].append(row)
        by_flow_relation[flow_relation(row)].append(row)
        by_regime[row.get('marketRegime', 'unknown')].append(row)

    aggregate = {
        'summary': summarize_group(all_rows),
        'flowCoverage': round(
            sum(1 for r in all_rows if (r.get('flow') or {}).get('available')) / len(all_rows), 3
        ) if all_rows else 0,
        'byProfile': {k: summarize_group(v) for k, v in sorted(by_profile.items())},
        'byFlowRelation': {k: summarize_group(v) for k, v in sorted(by_flow_relation.items())},
        'byMarketRegime': {k: summarize_group(v) for k, v in sorted(by_regime.items())},
        'sampleRegimes': {
            k: {
                'cutoff': v['cutoff'],
                'marketRegime': v['marketRegime'],
                'priceBreadth': v['priceBreadth'],
                'flowBreadth': v['flowBreadth'],
                'flowMedian': v['flowMedian'],
                'flowCoverage': v['flowCoverage'],
                'summary': v['summary'],
            }
            for k, v in samples.items()
        },
    }

    payload = {
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'method': (
            'Locked V24-Core validation batch on five previously uninspected June 2026 cutoffs. '
            'No V24 scoring weights, market-regime thresholds, first-5m OKX taker-flow logic, '
            'structural SL logic or dynamic RR rules were changed after Jul04/Jul02 outcomes. '
            'This batch only supplies new cutoff dates and aggregates performance by coin profile, '
            'microflow relation and market regime.'
        ),
        'isLockedValidation': True,
        'samples': samples,
        'aggregate': aggregate,
    }
    with open('data/blind_backtest_v24_validation.json', 'w') as f:
        json.dump(payload, f, indent=2)

    print(json.dumps({
        'aggregate': aggregate['summary'],
        'flowCoverage': aggregate['flowCoverage'],
        'samples': aggregate['sampleRegimes'],
        'byProfile': aggregate['byProfile'],
        'byFlowRelation': aggregate['byFlowRelation'],
        'byMarketRegime': aggregate['byMarketRegime'],
    }, indent=2))


if __name__ == '__main__':
    main()
