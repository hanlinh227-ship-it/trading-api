#!/usr/bin/env python3
'''V11 MTF runner: integrity repair, strict gates, learning registry.'''
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'scripts/v11_backtest_mtf.py'

spec = importlib.util.spec_from_file_location('v11mtf', P)
b = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(b)

# Canonical research gate. Environment variables may not weaken the >=80 threshold.
b.REQUIRED_WR = 80.0


def _selfcheck():
    if b.REQUIRED_WR < 80.0:
        raise AssertionError('REQUIRED_WR_WEAKENED')
    if set(b.ALLOWED_RR) != {1.0, 2.0}:
        raise AssertionError('RR_DOMAIN_INVALID')


def patch_outputs():
    report = json.loads(b.OUT.read_text(encoding='utf-8'))
    gate = json.loads(b.GATE.read_text(encoding='utf-8'))
    symbols = report.get('symbols') or {}

    registry = {
        'version': 'V11-MTF-LEARNING-REGISTRY-R4',
        'generatedAt': datetime.now(timezone.utc).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'policy': 'training/DEV/VALIDATION only; final holdout excluded from selection/tuning',
        'finalHoldoutExcluded': True,
        'selectionMethod': 'chronological DEV/VALIDATION profile ranking',
        'symbols': {},
    }

    current_passed = []
    current_failed = []
    for s, r in symbols.items():
        final = r.get('final') or {}
        exp = final.get('expectedDays', 0)
        trades = final.get('trades', 0)
        counts = final.get('dayCounts') or {}
        ok = bool(r.get('pass')) and bool(r.get('sourceExactInstrument')) and exp > 0 and exp <= trades <= 3 * exp
        if ok and counts:
            ok = len(counts) >= exp and all(1 <= int(v) <= 3 for v in counts.values())
        if ok:
            current_passed.append(s)
        else:
            current_failed.append(s)

        registry['symbols'][s] = {
            k: r.get(k) for k in (
                'market', 'source', 'sourceExactInstrument', 'dataError',
                'train', 'dev', 'validation', 'profile', 'selectionData', 'eligibleDays'
            )
        }

    b.REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')

    gate['learningRegistry'] = b.REGISTRY.name
    gate['currentGate'] = {
        'requiredFinalWR': 80.0,
        'allowedRR': [1, 2],
        'tradeCountDomain': '[eligibleFinalDays, 3*eligibleFinalDays]',
        'dailyCountDomain': '1..3 on every eligible final day',
        'exactInstrumentRequired': True,
        'holdoutExcludedFromTuning': True,
        'check': 'PASS' if len(current_failed) == 0 else 'STRICTER_FAIL',
    }
    gate['passingSymbols'] = current_passed
    gate['failingSymbols'] = current_failed
    gate['passCount'] = len(current_passed)
    gate['totalSymbols'] = len(symbols)
    gate['allPassed'] = len(current_passed) == len(symbols)
    b.GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    _selfcheck()
    rc = b.main()
    patch_outputs()
    raise SystemExit(rc)
