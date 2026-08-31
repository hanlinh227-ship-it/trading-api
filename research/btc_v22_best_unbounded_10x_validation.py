#!/usr/bin/env python3
"""Fresh 10-start validation of the historically best BTC V22 configuration.

No config optimization on these 10 validation starts.
Rules inherited from V22: $20 start, BTC TP=300 price units, 0.02->1.00,
+0.01 only after actual TP, one position, no SL/cut/trailing/timeout close.
Each sampled start runs to PASS99, BUST, or physical DATA_END. There is no
fixed-day completion deadline.
"""
from __future__ import annotations
import argparse, os, random, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_xau_btc_v21_vwap_unbounded as v21
import dual_xau_btc_v22_target99_adaptive as v22

BEST = v21.C(
    fast=5, slow=20, lb=8, rlo=42, rhi=72,
    early_mode='compression', mid_mode='momentum', late_mode='momentum',
    early_stable=24, early_h1=1, early_budget=1.8,
    early_vwap_win=48, early_vwap_max=1.4, early_reclaim=0.2,
    mid_vwap_win=48, mid_vwap_max=1.7, mid_confirm=0.05, mid_body=0.05,
    late_stable=24, late_h1=0, late_vwap_win=96, late_vwap_max=1.0, late_sep=0,
)
WARM = 700
N = 10


def seed_value(cli):
    if cli is not None:
        return cli
    rid = os.getenv('GITHUB_RUN_ID')
    att = os.getenv('GITHUB_RUN_ATTEMPT', '1')
    return int(rid) * 100 + int(att) if rid and rid.isdigit() else 22001001


def choose_starts(bars, seed):
    # No backtest time limit after a start. Reserve only 60d of physical future
    # history so late starts are not trivially DATA_END; this is not an exit cap.
    reserve = 60 * 24 * 12
    lo = WARM
    hi = len(bars) - reserve - 3
    if hi <= lo:
        raise RuntimeError(f'not enough BTC history: bars={len(bars)}')
    xs = list(range(lo, hi))
    random.Random(seed).shuffle(xs)
    out = []
    min_gap = 7 * 24 * 12
    for s in xs:
        if all(abs(s - x) >= min_gap for x in out):
            out.append(s)
        if len(out) == N:
            break
    if len(out) != N:
        raise RuntimeError(f'could only choose {len(out)} distinct starts')
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int)
    a = ap.parse_args()
    seed = seed_value(a.seed)
    bars = v21.b8.load()
    starts = choose_starts(bars, seed)
    print('=== BTC V22 HISTORICAL-BEST / FRESH UNBOUNDED 10X ===', flush=True)
    print(f'SEED {seed} range={bars[0].dt} -> {bars[-1].dt} bars={len(bars)}', flush=True)
    print('RULES startBalance=20 TPprice=300 lot=0.02->1.00 noSL noCut noTrailing noTimeoutClose', flush=True)
    print(f'FROZEN_BEST_CFG={BEST}', flush=True)
    results = []
    for j, s in enumerate(starts, 1):
        w = bars[s-WARM:]
        I = v21.prep(w)
        r = v22.run('BTC', w, BEST, I)
        # V22's elapsed days starts at w[0], so report elapsed from the actual sampled start.
        actual_start = v21.DT(bars[s].dt)
        end_dt = v21.DT(r.when)
        elapsed = max(0.0, (end_dt - actual_start).total_seconds() / 86400.0)
        if r.done:
            reason = 'PASS99'
        elif r.bust:
            reason = 'BUST'
        else:
            reason = 'DATA_END'
        results.append((s, r, reason, elapsed))
        print(
            f'BTC_TEST{j:02d} start={bars[s].dt} status={reason} TP={r.tps}/99 '
            f'days={elapsed:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when}',
            flush=True,
        )
    p = sum(r.done for _, r, _, _ in results)
    b = sum(r.bust for _, r, _, _ in results)
    de = N - p - b
    tps = [r.tps for _, r, _, _ in results]
    print(
        f'BTC_FINAL PASS={p}/10 BUST={b}/10 DATA_END={de}/10 '
        f'TP_SUM={sum(tps)} MED_TP={statistics.median(tps):.1f} '
        f'MAX_TP={max(tps)} MIN_TP={min(tps)}',
        flush=True,
    )
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
