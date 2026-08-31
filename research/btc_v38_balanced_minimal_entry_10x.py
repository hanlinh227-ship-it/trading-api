#!/usr/bin/env python3
"""BTC V38 — balanced minimal-indicator entry.
Research only. Uses V36 compound/SL state machine unchanged.
Decision inputs remain EMA20, EMA60, VWAP96, ATR plus raw candle/price action.
No structure-SL filter, no RSI/MACD, no composite score.
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
        (8, 12),
        (0.10, 0.16),
        (0.34, 0.44),
        (0.08, 0.14),
        ((180.0, 60.0), (240.0, 80.0)),
    ):
        yield v36.Cfg(age, sep, cd, pt, rec[0], rec[1])


def signal(i, b, c, I, lot, recovery):
    if i < v36.WARM + 16:
        return 0
    atr = I['a'][i]
    if atr < 60 or atr > 680:
        return 0

    d = v36.established_trend(i, b, I, c)
    if not d:
        return 0

    E, V = I['e'], I['v']
    e20, e60, vw = E[20][i], E[60][i], V[96][i]
    value = (e20 + vw) / 2.0
    x, p = b[i], b[i-1]

    # Same indicators only: ensure the value zone itself is on the correct side
    # of the slow trend, without requiring a perfect stacked arrangement.
    if d > 0 and value <= e60 + 0.03 * atr:
        return 0
    if d < 0 and value >= e60 - 0.03 * atr:
        return 0

    # Simple raw-price momentum: trend should have actually moved in its direction.
    mom12 = b[i].c - b[i-12].c
    mom_need = (0.24 if recovery else 0.14) * atr
    if d > 0 and mom12 <= mom_need:
        return 0
    if d < 0 and mom12 >= -mom_need:
        return 0

    tighten = 0.84 if recovery else (0.88 if lot > 0.50 else 0.93 if lot > 0.20 else 1.0)
    if abs(x.c - value) / atr > c.close_dist * tighten:
        return 0
    if (x.h - x.l) / atr > 1.02 or abs(x.c - x.o) / atr > 0.62:
        return 0

    pull = b[i-4:i]
    if d > 0:
        if min(z.l for z in pull) > value + c.pull_tol * atr:
            return 0
        if min(z.l for z in pull) < e60 - 0.50 * atr:
            return 0
        if not (x.c > x.o and x.c > value and x.c >= p.c):
            return 0
        loc = (x.c - x.l) / max(x.h - x.l, 1e-9)
        if loc < 0.54:
            return 0
    else:
        if max(z.h for z in pull) < value - c.pull_tol * atr:
            return 0
        if max(z.h for z in pull) > e60 + 0.50 * atr:
            return 0
        if not (x.c < x.o and x.c < value and x.c <= p.c):
            return 0
        loc = (x.h - x.c) / max(x.h - x.l, 1e-9)
        if loc < 0.54:
            return 0

    # Recent raw range only checks whether TP300 is plausible in this regime.
    recent = b[max(0, i-30):i]
    if max(z.h for z in recent) - min(z.l for z in recent) < 320:
        return 0
    return d


def entry_ok(sig_i, entry, b, c, I, lot, recovery):
    atr = max(I['a'][sig_i], 1e-9)
    value = (I['e'][20][sig_i] + I['v'][96][sig_i]) / 2.0
    tighten = 0.84 if recovery else (0.88 if lot > 0.50 else 0.93 if lot > 0.20 else 1.0)
    cap = min(0.60, (c.close_dist + 0.14) * tighten)
    if abs(entry - value) / atr > cap:
        return False
    if abs(entry - b[sig_i].c) / atr > 0.20:
        return False
    return True


def rank(a):
    wins = sum(x.tp_count for x in a)
    losses = sum(x.sl_count for x in a)
    ratio = wins / max(losses, 1)
    return (
        sum(x.done for x in a),
        -sum(x.bust for x in a),
        min(x.max_lot for x in a),
        statistics.median(x.max_lot for x in a),
        statistics.median(x.balance for x in a),
        wins,
        ratio,
        min(x.min_balance for x in a),
        -statistics.median(x.dd for x in a),
    )


def main():
    v36.signal = signal
    v36.entry_ok = entry_ok
    b = data.load()
    I = v21.prep(b)
    cal = v30.calibration_starts(b)
    cs = list(cfgs())
    print('=== BTC V38 BALANCED MINIMAL ENTRY ===', flush=True)
    print('EMA20 EMA60 VWAP96 ATR + price action only; NO structure SL; NO composite score', flush=True)
    print('LOCKED V36 exact-money compound/recovery state machine', flush=True)
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
