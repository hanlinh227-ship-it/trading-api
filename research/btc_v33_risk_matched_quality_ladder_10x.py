#!/usr/bin/env python3
"""BTC V33 — risk-matched quality ladder.

V32 exposed a key mismatch: as lot rises, locked SL money approaches current TP
money, so the required win rate rises toward 50%. V33 therefore raises entry
quality with lot instead of loosening it. Recovery below $20 uses 0.01 with a
higher RR and stricter signal. Compound/retry/step-down mechanics remain V32.
"""
from __future__ import annotations

import itertools
import statistics
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import btc_v32_dynamic_compound_sl_10x as v32
import btc_v30_complete_data_quality_entry_10x as v30
import btc_binance_m5_full_loader as data
import dual_xau_btc_v21_vwap_unbounded as v21


def cfgs():
    # 16 configs only; validation windows remain untouched.
    for early, high, dist, rec in itertools.product(
        (5.6, 6.0),
        (6.4, 6.8),
        (0.50, 0.65),
        ((240.0, 90.0), (300.0, 100.0)),
    ):
        yield v32.Cfg(early, high, dist, 0.04, rec[0], rec[1])


def threshold(lot: float, c: v32.Cfg, recovery: bool) -> float:
    if recovery:
        return max(6.4, c.early_score + 0.4)
    if lot <= 0.05 + 1e-9:
        return c.early_score
    if lot <= 0.20 + 1e-9:
        return max(6.0, c.early_score + 0.3)
    if lot <= 0.50 + 1e-9:
        return c.mid_score
    return c.mid_score + 0.4


def signal(i, b, c: v32.Cfg, I, lot: float, in_recovery: bool) -> int:
    if i < v32.WARM:
        return 0
    sc, val, atr = v30.authority(i, b, I)
    need = threshold(lot, c, in_recovery)
    if abs(sc) < need:
        return 0
    if atr < 75 or atr > 650:
        return 0

    d = 1 if sc > 0 else -1
    x, p, pp = b[i], b[i - 1], b[i - 2]
    E, V = I['e'], I['v']
    dist = (x.c - val) / atr
    rng = (x.h - x.l) / atr
    body = abs(x.c - x.o) / atr
    if abs(dist) > c.max_dist or rng > 1.35 or body > 0.90:
        return 0

    strict = in_recovery or lot > 0.20 + 1e-9
    if d > 0:
        if not (E[12][i] > E[36][i] and E[60][i] > E[150][i]):
            return 0
        if not (E[20][i] > E[20][i - 12] and E[60][i] > E[60][i - 24]):
            return 0
        if V[96][i] <= V[96][i - 12]:
            return 0
        if strict and not (E[8][i] > E[20][i] > E[36][i]):
            return 0
        if p.l > val + 0.10 * atr:
            return 0
        if not (p.c >= val - 0.15 * atr and x.c > x.o and x.c > p.h + c.confirm * atr and x.c > val):
            return 0
        if pp.c > p.c and pp.h > p.h:
            return 0
    else:
        if not (E[12][i] < E[36][i] and E[60][i] < E[150][i]):
            return 0
        if not (E[20][i] < E[20][i - 12] and E[60][i] < E[60][i - 24]):
            return 0
        if V[96][i] >= V[96][i - 12]:
            return 0
        if strict and not (E[8][i] < E[20][i] < E[36][i]):
            return 0
        if p.h < val - 0.10 * atr:
            return 0
        if not (p.c <= val + 0.15 * atr and x.c < x.o and x.c < p.l - c.confirm * atr and x.c < val):
            return 0
        if pp.c < p.c and pp.l < p.l:
            return 0

    recent = b[max(0, i - 24):i]
    if max(z.h for z in recent) - min(z.l for z in recent) < 380:
        return 0
    return d


def rank(rs):
    passes = sum(r.done for r in rs)
    busts = sum(r.bust for r in rs)
    worst_lot = min(r.max_lot for r in rs)
    med_lot = statistics.median(r.max_lot for r in rs)
    min_bal = min(r.min_balance for r in rs)
    med_bal = statistics.median(r.balance for r in rs)
    tp_sum = sum(r.tp_count for r in rs)
    med_dd = statistics.median(r.dd for r in rs)
    return (passes, -busts, worst_lot, med_lot, min_bal, med_bal, tp_sum, -med_dd)


def main():
    # Patch V32's signal lookup only; its locked state machine is reused unchanged.
    v32.signal = signal
    b = data.load()
    I = v21.prep(b)
    cal = v30.calibration_starts(b)
    candidates = list(cfgs())
    print('=== BTC V33 RISK-MATCHED QUALITY LADDER / COMPLETE BINANCE M5 ===', flush=True)
    print('LOCKED compoundTP300 dynamicSL firstSLretry firstTPrepair secondTPadvance secondSLstepDown below20=0.01 noCooldown stopAfter1.00LotTP', flush=True)
    print(f'CAL_CONFIGS {len(candidates)}', flush=True)

    best = None
    for n, c in enumerate(candidates, 1):
        rs = [v32.run(b, s, c, I) for s in cal]
        rk = rank(rs)
        if best is None or rk > best[0]:
            best = (rk, c, rs)
        if n % 4 == 0 or n == len(candidates):
            print(f'CAL_PROGRESS {n}/{len(candidates)} best={best[0]} cfg={best[1]}', flush=True)

    rk, c, _ = best
    print('BEST_CFG', c, 'CAL_RANK', rk, flush=True)
    starts = v30.fresh_starts(b)
    rs = [v32.run(b, s, c, I) for s in starts]
    for j, (s, r) in enumerate(zip(starts, rs), 1):
        print(
            f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} maxLot={r.max_lot:.2f} '
            f'currentLot={r.current_lot:.2f} balance={r.balance:.2f} minBal={r.min_balance:.2f} '
            f'TP={r.tp_count} SL={r.sl_count} recoveryEntries={r.recovery_entries} '
            f'recoveryTP={r.recovery_tps} trades={r.trades} DD={r.dd:.2f}% days={r.days:.2f} end={r.when}',
            flush=True,
        )

    print(
        f'BTC_FINAL PASS_1LOT={sum(r.done for r in rs)}/10 BUST={sum(r.bust for r in rs)}/10 '
        f'DATA_END={sum(r.reason == "DATA_END" for r in rs)}/10 '
        f'MED_MAX_LOT={statistics.median(r.max_lot for r in rs):.2f} MAX_LOT={max(r.max_lot for r in rs):.2f} '
        f'MIN_MAX_LOT={min(r.max_lot for r in rs):.2f} TP_SUM={sum(r.tp_count for r in rs)} '
        f'SL_SUM={sum(r.sl_count for r in rs)} MED_FINAL_BAL={statistics.median(r.balance for r in rs):.2f} '
        f'BEST_CFG={c}', flush=True,
    )


if __name__ == '__main__':
    main()
