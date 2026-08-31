#!/usr/bin/env python3
"""BTC V32 — dynamic compound ladder with SL/recovery state machine.

Research only. No live execution changes.

Locked compound rules (balance >= $20):
- BTC TP = 300 price units.
- Start/restart at 0.02 lot.
- Normal TP: +0.01 lot.
- SL money at current lot L = TP money of previous lot = (L-0.01)*300.
- First SL at a lot: retry the same lot.
- After that SL, first TP repairs the SL and keeps the same lot; second TP advances +0.01.
- A second SL before repair completes: reduce lot by 0.01; the lower lot starts clean.
- Every new/lower lot recalculates its own SL from its immediately lower lot.
- No martingale and no jump back to a prior peak lot.

Recovery rules (balance < $20):
- Force 0.01 lot; recovery TP/SL are tuned only on calibration windows.
- Stay at 0.01 until realized balance >= $20, then reset cleanly to 0.02.

Execution/timing:
- One position at a time, 24/7, no session/news/daily cap/cooldown/timeout.
- Re-entry has NO artificial 5-minute wait. With M5 OHLC data, earliest unbiased
  re-entry is the next available M5 bar; same-bar re-entry is not simulated because
  intrabar tick ordering is unavailable.
- If TP and SL are both touched in one M5 bar, SL is applied first (conservative).

The ladder itself has no maximum lot. This validation deliberately stops only after
an actual 1.00-lot trade hits TP, as requested for the 10-window milestone test.
"""
from __future__ import annotations

import itertools
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import btc_binance_m5_full_loader as data
import btc_v30_complete_data_quality_entry_10x as v30
import dual_xau_btc_v21_vwap_unbounded as v21

BASE_BAL = 20.0
BASE_LOT = 0.02
RECOVERY_LOT = 0.01
LOT_STEP = 0.01
COMPOUND_TP = 300.0
MILESTONE_LOT = 1.00
WARM = 700


@dataclass(frozen=True)
class Cfg:
    early_score: float
    mid_score: float
    max_dist: float
    confirm: float
    recovery_tp: float
    recovery_sl: float


@dataclass
class R:
    done: bool
    bust: bool
    reason: str
    balance: float
    min_balance: float
    max_lot: float
    current_lot: float
    tp_count: int
    sl_count: int
    recovery_entries: int
    recovery_tps: int
    trades: int
    dd: float
    days: float
    when: str


def cfgs():
    # 32 configurations. Validation windows are never used for selection.
    recoveries = ((120.0, 60.0), (180.0, 90.0))
    for early, mid, dist, conf, rec in itertools.product(
        (5.2, 6.0), (4.6, 5.2), (0.55, 0.75), (0.02, 0.04), recoveries
    ):
        yield Cfg(early, mid, dist, conf, rec[0], rec[1])


def phase_threshold(lot: float, c: Cfg) -> float:
    if lot <= 0.10 + 1e-9:
        return c.early_score
    if lot <= 0.50 + 1e-9:
        return c.mid_score
    return max(4.2, c.mid_score - 0.4)


def signal(i, b, c: Cfg, I, lot: float, in_recovery: bool) -> int:
    if i < WARM:
        return 0
    sc, val, atr = v30.authority(i, b, I)
    need = max(c.early_score, 5.8) if in_recovery else phase_threshold(lot, c)
    if abs(sc) < need:
        return 0

    # Avoid both dead/noisy conditions and extreme expansion.
    if atr < 65 or atr > (430 if lot <= 0.10 else 750):
        return 0
    d = 1 if sc > 0 else -1
    x, p = b[i], b[i - 1]
    E = I['e']
    rng = (x.h - x.l) / atr
    body = abs(x.c - x.o) / atr
    dist = (x.c - val) / atr
    if rng > 1.60 or body > 1.15 or abs(dist) > c.max_dist:
        return 0

    # HTF/trend authority. Do not take counter-trend M5 continuation entries.
    if d > 0:
        if not (E[12][i] > E[36][i] and E[60][i] > E[150][i]):
            return 0
        if E[36][i] <= E[36][i - 12]:
            return 0
        # Pullback into value, then closed-bar continuation confirmation.
        if p.l > val + 0.18 * atr:
            return 0
        if not (x.c > x.o and x.c > p.h + c.confirm * atr and x.c > val):
            return 0
    else:
        if not (E[12][i] < E[36][i] and E[60][i] < E[150][i]):
            return 0
        if E[36][i] >= E[36][i - 12]:
            return 0
        if p.h < val - 0.18 * atr:
            return 0
        if not (x.c < x.o and x.c < p.l - c.confirm * atr and x.c < val):
            return 0

    # A 300-price target must be plausible from recent movement. Recovery uses a
    # smaller target, but we keep the same quality gate rather than loosen entries.
    recent = b[max(0, i - 24):i]
    if max(z.h for z in recent) - min(z.l for z in recent) < 340:
        return 0
    return d


def compound_sl_usd(lot: float) -> float:
    prev = round(max(0.01, lot - LOT_STEP), 2)
    return prev * COMPOUND_TP


def run(b, start: int, c: Cfg, I) -> R:
    bal = BASE_BAL
    peak = BASE_BAL
    min_bal = BASE_BAL
    dd = 0.0
    lot = BASE_LOT
    max_lot = lot
    tp_count = sl_count = recovery_entries = recovery_tps = trades = 0
    pos = None
    st = b[start].ts
    when = b[start].dt

    # repair_active means this exact lot has suffered its first SL and must earn
    # two TPs before it may advance. repair_tp is 0 or 1.
    repair_active = False
    repair_tp = 0

    for i in range(max(start, WARM + 2), len(b)):
        z = b[i]
        in_recovery = bal < BASE_BAL - 1e-9

        if in_recovery:
            # Hard override: old compound stage/debt is discarded below $20.
            lot = RECOVERY_LOT
            repair_active = False
            repair_tp = 0
        elif lot < BASE_LOT - 1e-9:
            # Crossing back to >=$20 always starts a fresh compound cycle at 0.02.
            lot = BASE_LOT
            repair_active = False
            repair_tp = 0

        if pos is None:
            d = signal(i - 1, b, c, I, lot, in_recovery)
            if not d:
                continue
            entry = z.o
            tp_dist = c.recovery_tp if in_recovery else COMPOUND_TP
            sl_dist = c.recovery_sl if in_recovery else compound_sl_usd(lot) / lot
            pos = (d, entry, lot, tp_dist, sl_dist, in_recovery)
            trades += 1
            if in_recovery:
                recovery_entries += 1

        d, en, L, tp_dist, sl_dist, opened_recovery = pos
        stop = en - d * sl_dist
        target = en + d * tp_dist
        sl_hit = z.l <= stop if d > 0 else z.h >= stop
        tp_hit = z.h >= target if d > 0 else z.l <= target

        # Conservative same-bar ordering: SL wins if both were touched.
        if sl_hit:
            loss_usd = L * sl_dist
            bal -= loss_usd
            min_bal = min(min_bal, bal)
            sl_count += 1
            when = z.dt
            pos = None
            dd = max(dd, (peak - bal) / peak if peak > 0 else 1.0)
            if bal <= 0:
                return R(False, True, 'BUST', bal, min_bal, max_lot, L, tp_count,
                         sl_count, recovery_entries, recovery_tps, trades, dd * 100,
                         (z.ts - st) / 86400, z.dt)

            if bal < BASE_BAL - 1e-9:
                # Recovery override; compound history is intentionally wiped.
                lot = RECOVERY_LOT
                repair_active = False
                repair_tp = 0
                continue

            # Compound SL state machine.
            if repair_active:
                # This is the second SL before the two-TP repair completed.
                lot = round(max(BASE_LOT, L - LOT_STEP), 2)
                repair_active = False
                repair_tp = 0
            else:
                # First SL: retry exactly the same lot once / until repair resolves.
                lot = L
                repair_active = True
                repair_tp = 0
            continue

        if tp_hit:
            profit = L * tp_dist
            bal += profit
            peak = max(peak, bal)
            min_bal = min(min_bal, bal)
            tp_count += 1
            when = z.dt
            pos = None
            dd = max(dd, (peak - bal) / peak if peak > 0 else 0.0)

            if opened_recovery:
                recovery_tps += 1
                if bal >= BASE_BAL - 1e-9:
                    lot = BASE_LOT
                    repair_active = False
                    repair_tp = 0
                else:
                    lot = RECOVERY_LOT
                continue

            # Requested milestone: stop only after a real 1.00-lot TP.
            if L >= MILESTONE_LOT - 1e-9:
                return R(True, False, 'PASS_1LOT', bal, min_bal, max(max_lot, L), L,
                         tp_count, sl_count, recovery_entries, recovery_tps, trades,
                         dd * 100, (z.ts - st) / 86400, z.dt)

            if repair_active:
                if repair_tp == 0:
                    # First TP after an SL only repairs the loss; same lot again.
                    repair_tp = 1
                    lot = L
                else:
                    # Second TP completes repair and progression resumes.
                    lot = round(L + LOT_STEP, 2)
                    repair_active = False
                    repair_tp = 0
            else:
                lot = round(L + LOT_STEP, 2)
            max_lot = max(max_lot, lot)
            continue

        # Mark-to-market DD while position remains open.
        adverse = max(0.0, en - z.l) if d > 0 else max(0.0, z.h - en)
        floating = bal - adverse * L
        dd = max(dd, (peak - floating) / peak if peak > 0 else 1.0)
        if floating <= 0:
            return R(False, True, 'BUST_FLOATING', bal, min_bal, max_lot, L,
                     tp_count, sl_count, recovery_entries, recovery_tps, trades,
                     dd * 100, (z.ts - st) / 86400, z.dt)

    return R(False, False, 'DATA_END', bal, min_bal, max_lot, lot, tp_count,
             sl_count, recovery_entries, recovery_tps, trades, dd * 100,
             (b[-1].ts - st) / 86400, when)


def rank(rs):
    passes = sum(r.done for r in rs)
    busts = sum(r.bust for r in rs)
    worst_lot = min(r.max_lot for r in rs)
    med_lot = statistics.median(r.max_lot for r in rs)
    med_bal = statistics.median(r.balance for r in rs)
    med_dd = statistics.median(r.dd for r in rs)
    tp_sum = sum(r.tp_count for r in rs)
    # Survival and 1-lot completion dominate trade count / speed.
    return (passes, -busts, worst_lot, med_lot, med_bal, tp_sum, -med_dd)


def main():
    b = data.load()
    I = v21.prep(b)
    cal = v30.calibration_starts(b)
    candidates = list(cfgs())
    print('=== BTC V32 DYNAMIC COMPOUND SL / COMPLETE BINANCE M5 ===', flush=True)
    print('RULES base=$20 compoundTP=300 start=0.02 step=0.01; SL_USD=prevLot*300; firstSL retry; firstTP repair; secondTP advance; secondSL stepDown; below20=0.01 recovery; noCooldown; stopAfter1.00LotTP', flush=True)
    print(f'CAL_CONFIGS {len(candidates)}', flush=True)

    best = None
    for n, c in enumerate(candidates, 1):
        rs = [run(b, s, c, I) for s in cal]
        rk = rank(rs)
        if best is None or rk > best[0]:
            best = (rk, c, rs)
        if n % 8 == 0 or n == len(candidates):
            print(f'CAL_PROGRESS {n}/{len(candidates)} best={best[0]} cfg={best[1]}', flush=True)

    rk, c, _ = best
    print('BEST_CFG', c, 'CAL_RANK', rk, flush=True)

    # Same ten locked validation windows as V30/V31; never changed after results.
    starts = v30.fresh_starts(b)
    rs = [run(b, s, c, I) for s in starts]
    for j, (s, r) in enumerate(zip(starts, rs), 1):
        print(
            f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} '
            f'maxLot={r.max_lot:.2f} currentLot={r.current_lot:.2f} '
            f'balance={r.balance:.2f} minBal={r.min_balance:.2f} '
            f'TP={r.tp_count} SL={r.sl_count} recoveryEntries={r.recovery_entries} '
            f'recoveryTP={r.recovery_tps} trades={r.trades} DD={r.dd:.2f}% '
            f'days={r.days:.2f} end={r.when}', flush=True
        )

    print(
        f'BTC_FINAL PASS_1LOT={sum(r.done for r in rs)}/10 '
        f'BUST={sum(r.bust for r in rs)}/10 '
        f'DATA_END={sum(r.reason == "DATA_END" for r in rs)}/10 '
        f'MED_MAX_LOT={statistics.median(r.max_lot for r in rs):.2f} '
        f'MAX_LOT={max(r.max_lot for r in rs):.2f} '
        f'MIN_MAX_LOT={min(r.max_lot for r in rs):.2f} '
        f'TP_SUM={sum(r.tp_count for r in rs)} SL_SUM={sum(r.sl_count for r in rs)} '
        f'MED_FINAL_BAL={statistics.median(r.balance for r in rs):.2f} '
        f'BEST_CFG={c}', flush=True
    )


if __name__ == '__main__':
    main()
