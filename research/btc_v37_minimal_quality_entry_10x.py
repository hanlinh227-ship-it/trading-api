#!/usr/bin/env python3
"""BTC V37 — minimal indicators, stricter trend-quality/pullback entry.
Research only. Reuses V36 compound/recovery/SL state machine unchanged.
Indicators remain only EMA20/EMA60, VWAP96 and ATR. Additional quality is raw
price-action efficiency, not another indicator family.
"""
from __future__ import annotations

import itertools
import statistics
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import btc_v36_minimal_entry_dynamic_compound_10x as v36
import btc_v30_complete_data_quality_entry_10x as v30
import btc_binance_m5_full_loader as data
import dual_xau_btc_v21_vwap_unbounded as v21


def cfgs():
    for age, sep, cd, pt, rec in itertools.product(
        (12, 18),
        (0.14, 0.20),
        (0.30, 0.38),
        (0.05, 0.10),
        ((180.0, 60.0), (240.0, 80.0)),
    ):
        yield v36.Cfg(age, sep, cd, pt, rec[0], rec[1])


def price_efficiency(i, b, n=24):
    if i < n:
        return 0.0, 0.0
    net = b[i].c - b[i-n].c
    path = sum(abs(b[k].c - b[k-1].c) for k in range(i-n+1, i+1))
    return net, abs(net) / max(path, 1e-9)


def signal(i, b, c, I, lot, recovery):
    if i < v36.WARM + 24:
        return 0
    atr = I['a'][i]
    if atr < 60 or atr > 650:
        return 0

    d = v36.established_trend(i, b, I, c)
    if not d:
        return 0

    E, V = I['e'], I['v']
    e20, e60, vw = E[20][i], E[60][i], V[96][i]
    value = (e20 + vw) / 2.0

    # EMA/VWAP must agree on the same side of the slower trend.
    if d > 0 and not (e20 > e60 and vw > e60):
        return 0
    if d < 0 and not (e20 < e60 and vw < e60):
        return 0

    # Raw price-path efficiency rejects sideways churn without adding RSI/MACD/etc.
    net, eff = price_efficiency(i, b, 24)
    eff_need = 0.30 if recovery else (0.28 if lot > 0.20 else 0.23)
    if eff < eff_need or (net <= 0 if d > 0 else net >= 0):
        return 0

    x, p = b[i], b[i-1]
    tighten = 0.82 if recovery else (0.86 if lot > 0.50 else 0.92 if lot > 0.20 else 1.0)
    if abs(x.c - value) / atr > c.close_dist * tighten:
        return 0
    if (x.h - x.l) / atr > 0.90 or abs(x.c - x.o) / atr > 0.55:
        return 0

    pull = b[i-4:i]
    if d > 0:
        if min(z.l for z in pull) > value + c.pull_tol * atr:
            return 0
        # Pullback may probe value, but should not materially break EMA60.
        if min(z.l for z in pull) < e60 - 0.30 * atr:
            return 0
        if not (x.c > x.o and x.c > value and x.c > p.c):
            return 0
        # Confirmation must close in upper portion, but remain a small/controlled bar.
        loc = (x.c - x.l) / max(x.h - x.l, 1e-9)
        if loc < 0.58:
            return 0
    else:
        if max(z.h for z in pull) < value - c.pull_tol * atr:
            return 0
        if max(z.h for z in pull) > e60 + 0.30 * atr:
            return 0
        if not (x.c < x.o and x.c < value and x.c < p.c):
            return 0
        loc = (x.h - x.c) / max(x.h - x.l, 1e-9)
        if loc < 0.58:
            return 0

    recent = b[max(0, i-30):i]
    if max(z.h for z in recent) - min(z.l for z in recent) < 330:
        return 0
    return d


def rank(a):
    wins = sum(x.tp_count for x in a)
    losses = sum(x.sl_count for x in a)
    edge_ratio = wins / max(losses, 1)
    return (
        sum(x.done for x in a),
        -sum(x.bust for x in a),
        min(x.max_lot for x in a),
        statistics.median(x.max_lot for x in a),
        statistics.median(x.balance for x in a),
        edge_ratio,
        min(x.min_balance for x in a),
        -statistics.median(x.dd for x in a),
    )


def main():
    v36.signal = signal
    b = data.load()
    I = v21.prep(b)
    cal = v30.calibration_starts(b)
    cs = list(cfgs())
    print('=== BTC V37 MINIMAL QUALITY ENTRY ===', flush=True)
    print('INDICATORS EMA20 EMA60 VWAP96 ATR only + raw price efficiency; NO structure SL; NO composite score', flush=True)
    print('LOCKED V36 compound/recovery exact-money SL state machine', flush=True)
    print(f'CAL_CONFIGS {len(cs)}', flush=True)
    best = None
    for n, c in enumerate(cs, 1):
        a = [v36.run(b, s, c, I) for s in cal]
        rk = rank(a)
        if best is None or rk > best[0]:
            best = (rk, c, a)
        if n % 8 == 0 or n == len(cs):
            print(f'CAL_PROGRESS {n}/{len(cs)} best={best[0]} cfg={best[1]}', flush=True)
    rk, c, _ = best
    print('BEST_CFG', c, 'CAL_RANK', rk, flush=True)

    starts = v30.fresh_starts(b)
    a = [v36.run(b, s, c, I) for s in starts]
    for j, (s, r) in enumerate(zip(starts, a), 1):
        print(
            f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} maxLot={r.max_lot:.2f} '
            f'currentLot={r.current_lot:.2f} balance={r.balance:.2f} minBal={r.min_balance:.2f} '
            f'TP={r.tp_count} SL={r.sl_count} recoveryEntries={r.recovery_entries} recoveryTP={r.recovery_tps} '
            f'trades={r.trades} rejectChase={r.reject_chase} balanceSteps={r.balance_steps} '
            f'DD={r.dd:.2f}% days={r.days:.2f} end={r.when}', flush=True
        )
    print(
        f'BTC_FINAL PASS_1LOT={sum(r.done for r in a)}/10 BUST={sum(r.bust for r in a)}/10 '
        f'DATA_END={sum(r.reason=="DATA_END" for r in a)}/10 '
        f'MED_MAX_LOT={statistics.median(r.max_lot for r in a):.2f} MAX_LOT={max(r.max_lot for r in a):.2f} '
        f'MIN_MAX_LOT={min(r.max_lot for r in a):.2f} TP_SUM={sum(r.tp_count for r in a)} '
        f'SL_SUM={sum(r.sl_count for r in a)} MED_FINAL_BAL={statistics.median(r.balance for r in a):.2f} '
        f'WINLOSS_COUNT_RATIO={sum(r.tp_count for r in a)/max(sum(r.sl_count for r in a),1):.3f} '
        f'REJECT_CHASE={sum(r.reject_chase for r in a)} BALANCE_STEPS={sum(r.balance_steps for r in a)} BEST_CFG={c}',
        flush=True,
    )


if __name__ == '__main__':
    main()
