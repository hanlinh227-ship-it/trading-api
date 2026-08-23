#!/usr/bin/env python3
"""Report-only V11 4-month backtest wrapper.

Uses the current V11 backtest engine but enforces the user's reporting protocol:
- each catalog symbol is independent;
- latest 122 days by default;
- max 3 executed entries per eligible UTC day;
- Forex/Metal/Index exclude Saturday/Sunday; Crypto remains 24/7;
- RR remains exactly 1:1 or 1:2 from the base engine;
- inclusive >=80.00% pass threshold on full/validation/OOS;
- no AI task creation, no Telegram unlock, no production deployment.
"""
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'scripts/v11_symbol_backtest_4m.py'
spec = importlib.util.spec_from_file_location('v11_bt_base', BASE)
bt = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(bt)

bt.VERSION = 'V11-4M-REPORT-ONLY-R2-MAX3'
bt.OUT = ROOT / 'data/v11_symbol_backtest_report_only.json'
bt.GATE = ROOT / 'data/v11_backtest_report_only_gate.json'
bt.GENERATED = ROOT / 'data/v11_backtest_report_only_profiles.js'

_original_generate = bt.generate_signals
_original_optimize = bt.optimize_symbol


def generate_signals_with_market(rows, market):
    sigs = _original_generate(rows, market)
    for s in sigs:
        s['market'] = market
    return sigs


def metric_max3(signals, outcomes, key, t0, t1):
    chosen = [s for s in signals if t0 <= s['ts'] < t1]
    chosen.sort(key=lambda s: s['entry_idx'])
    wins = losses = timeouts = 0
    last_exit = -1
    rr = key[1]
    per_day = defaultdict(int)
    traded_days = set()
    eligible_days = set()

    for s in chosen:
        market = s.get('market')
        day = datetime.fromtimestamp(s['ts'], timezone.utc).date().isoformat()
        weekday = datetime.fromtimestamp(s['ts'], timezone.utc).weekday()
        if market != 'crypto' and weekday >= 5:
            continue
        eligible_days.add(day)
        if per_day[day] >= 3:
            continue
        if s['entry_idx'] <= last_exit:
            continue
        o = outcomes[s['id']][key]
        status, exit_idx = o[0], o[1]
        if status == 'SKIP':
            continue
        per_day[day] += 1
        traded_days.add(day)
        last_exit = exit_idx
        if status == 'WIN':
            wins += 1
        elif status == 'LOSS':
            losses += 1
        else:
            timeouts += 1

    trades = wins + losses + timeouts
    wr = 100.0 * wins / trades if trades else 0.0
    mean_r = ((wins * rr) - losses - timeouts) / trades if trades else 0.0
    eligible = len(eligible_days)
    return {
        'trades': trades,
        'wins': wins,
        'losses': losses,
        'timeouts': timeouts,
        'winRate': round(wr, 2),
        'meanR': round(mean_r, 4),
        'daysTraded': len(traded_days),
        'eligibleSignalDays': eligible,
        'avgTradesPerEligibleSignalDay': round(trades / eligible, 3) if eligible else 0.0,
        'maxTradesInDay': max(per_day.values(), default=0),
    }


def optimize_inclusive(symbol, market, rows, start_ts, end_ts, source, data_error=None):
    r = _original_optimize(symbol, market, rows, start_ts, end_ts, source, data_error)
    if not r.get('profile'):
        return r
    reasons = [x for x in (r.get('reasons') or []) if x not in {
        'FULL_WR_NOT_ABOVE_80', 'VALIDATION_WR_NOT_ABOVE_80', 'OOS_WR_NOT_ABOVE_80'
    }]
    checks = (
        ('full4m', 'FULL_WR_BELOW_80'),
        ('validation', 'VALIDATION_WR_BELOW_80'),
        ('oos', 'OOS_WR_BELOW_80'),
    )
    for key, reason in checks:
        if float((r.get(key) or {}).get('winRate', 0.0)) < 80.0:
            reasons.append(reason)
    r['reasons'] = reasons
    r['pass'] = not reasons
    return r


bt.generate_signals = generate_signals_with_market
bt.metric_for = metric_max3
bt.optimize_symbol = optimize_inclusive
bt.REQUIRED_WR = 80.0


def postprocess():
    payload = json.loads(bt.OUT.read_text(encoding='utf-8'))
    meta = payload['meta']
    meta['requiredWinRateInclusive'] = 80.0
    meta['maxEntriesPerEligibleDay'] = 3
    meta['reportOnly'] = True
    meta['aiTaskCreation'] = False
    meta['weekendRule'] = 'Crypto 24/7; Forex/Metal/Index exclude Saturday/Sunday'
    meta['successRule'] = '100% catalog symbols independently >=80.00% on full4m, validation and untouched OOS'
    bt.OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    gate = json.loads(bt.GATE.read_text(encoding='utf-8'))
    gate.update({
        'requiredWinRateInclusive': 80.0,
        'maxEntriesPerEligibleDay': 3,
        'reportOnly': True,
        'aiTaskCreation': False,
    })
    bt.GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    rc = bt.main()
    postprocess()
    raise SystemExit(rc)
