#!/usr/bin/env python3
"""BTC V36 — minimal-indicator anti-FOMO entry + dynamic compound ladder.

Research only. No production/live execution changes.

Entry uses only:
- EMA20 / EMA60: established trend and slope.
- VWAP96: value / pullback reference.
- ATR: normalize volatility and chase distance.
- Price action: pullback -> controlled reclaim/rejection trigger.

No RSI/MACD, no composite authority score, no swing/structure SL filter.
Compound mechanics remain locked:
- >=$20: TP=300 BTC price units, start/restart 0.02, +0.01 progression.
- SL money at lot L = exact TP money of previous lot = (L-0.01)*300.
- first SL retries same lot; first TP repairs; second TP advances; second SL steps down.
- below $20: 0.01 recovery until balance >=$20, then fresh 0.02 cycle.
- no cooldown; M5 backtest can re-enter on next M5 bar only.
- no fixed maximum lot; this validation stops after an actual 1.00-lot TP.
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
REC_LOT = 0.01
STEP = 0.01
TP = 300.0
MILESTONE = 1.00
WARM = 700


@dataclass(frozen=True)
class Cfg:
    trend_age: int
    sep_min: float
    close_dist: float
    pull_tol: float
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
    reject_chase: int
    balance_steps: int
    dd: float
    days: float
    when: str


def cfgs():
    # 32 calibration-only configs. The 10 validation windows stay locked.
    for age, sep, cd, pt, rec in itertools.product(
        (6, 10),
        (0.08, 0.14),
        (0.42, 0.55),
        (0.08, 0.14),
        ((180.0, 60.0), (240.0, 80.0)),
    ):
        yield Cfg(age, sep, cd, pt, rec[0], rec[1])


def compound_sl_usd(lot: float) -> float:
    return round(max(0.01, lot - STEP), 2) * TP


def sl_dist(lot: float, c: Cfg, recovery: bool) -> float:
    return c.recovery_sl if recovery else compound_sl_usd(lot) / lot


def normalize_lot(lot: float, bal: float) -> tuple[float, int]:
    """No fixed max lot. Step down only if exact-money SL is larger than balance reserve."""
    steps = 0
    reserve = max(1.0, 0.05 * bal)
    while lot > BASE_LOT + 1e-9 and compound_sl_usd(lot) > max(0.0, bal - reserve):
        lot = round(lot - STEP, 2)
        steps += 1
    return lot, steps


def established_trend(i, b, I, c: Cfg) -> int:
    E = I['e']
    V = I['v']
    A = I['a']
    atr = max(A[i], 1e-9)
    e20 = E[20]
    e60 = E[60]
    vw = V[96]

    # Avoid a fresh EMA cross: relationship must already exist for trend_age bars.
    long_now = e20[i] > e60[i]
    short_now = e20[i] < e60[i]
    if long_now:
        if any(e20[k] <= e60[k] for k in range(i - c.trend_age + 1, i + 1)):
            return 0
        if not (e20[i] > e20[i-6] and e60[i] > e60[i-12] and vw[i] > vw[i-8]):
            return 0
        sep = (e20[i] - e60[i]) / atr
        if sep < c.sep_min or sep > 1.60:
            return 0
        return 1
    if short_now:
        if any(e20[k] >= e60[k] for k in range(i - c.trend_age + 1, i + 1)):
            return 0
        if not (e20[i] < e20[i-6] and e60[i] < e60[i-12] and vw[i] < vw[i-8]):
            return 0
        sep = (e60[i] - e20[i]) / atr
        if sep < c.sep_min or sep > 1.60:
            return 0
        return -1
    return 0


def signal(i, b, c: Cfg, I, lot: float, recovery: bool) -> int:
    if i < WARM + 12:
        return 0
    A = I['a']
    E = I['e']
    V = I['v']
    atr = A[i]
    if atr < 60 or atr > 700:
        return 0

    d = established_trend(i, b, I, c)
    if not d:
        return 0

    e20 = E[20][i]
    vw = V[96][i]
    value = (e20 + vw) / 2.0
    x = b[i]
    p = b[i-1]

    # High lots and recovery demand slightly cleaner entries without adding indicators.
    tighten = 0.82 if recovery else (0.86 if lot > 0.50 else 0.92 if lot > 0.20 else 1.0)
    close_cap = c.close_dist * tighten

    # Anti-FOMO: signal bar must remain close to value and not be an expansion candle.
    if abs(x.c - value) / atr > close_cap:
        return 0
    if (x.h - x.l) / atr > 1.15 or abs(x.c - x.o) / atr > 0.70:
        return 0

    # Require a genuine pullback into EMA20/VWAP value during recent bars.
    pull = b[i-4:i]
    if d > 0:
        if min(z.l for z in pull) > value + c.pull_tol * atr:
            return 0
        # Controlled reclaim: close back above value, bullish, but do not chase breakout highs.
        if not (x.c > x.o and x.c > value + 0.01 * atr and x.c >= p.c):
            return 0
        # Reject a bar that closes at an overextended extreme after the pullback.
        if (x.c - x.l) / max(x.h - x.l, 1e-9) > 0.92 and (x.h - x.l) / atr > 0.85:
            return 0
    else:
        if max(z.h for z in pull) < value - c.pull_tol * atr:
            return 0
        if not (x.c < x.o and x.c < value - 0.01 * atr and x.c <= p.c):
            return 0
        if (x.h - x.c) / max(x.h - x.l, 1e-9) > 0.92 and (x.h - x.l) / atr > 0.85:
            return 0

    # TP300 must be plausible in the current regime, using raw price movement only.
    recent = b[max(0, i-30):i]
    if max(z.h for z in recent) - min(z.l for z in recent) < 330:
        return 0
    return d


def entry_ok(sig_i: int, entry: float, b, c: Cfg, I, lot: float, recovery: bool) -> bool:
    atr = max(I['a'][sig_i], 1e-9)
    value = (I['e'][20][sig_i] + I['v'][96][sig_i]) / 2.0
    tighten = 0.82 if recovery else (0.86 if lot > 0.50 else 0.92 if lot > 0.20 else 1.0)
    entry_cap = min(0.65, (c.close_dist + 0.12) * tighten)
    if abs(entry - value) / atr > entry_cap:
        return False
    if abs(entry - b[sig_i].c) / atr > 0.18:
        return False
    return True


def run(b, start: int, c: Cfg, I) -> R:
    bal = peak = minbal = BASE_BAL
    dd = 0.0
    lot = BASE_LOT
    maxlot = lot
    pos = None
    tp = sl = rent = rtp = tr = rch = bstep = 0
    repair = False
    repair_tp = 0
    st = b[start].ts
    when = b[start].dt

    for i in range(max(start, WARM + 12), len(b)):
        z = b[i]
        recovery = bal < BASE_BAL - 1e-9
        if recovery:
            lot = REC_LOT
            repair = False
            repair_tp = 0
        else:
            if lot < BASE_LOT - 1e-9:
                lot = BASE_LOT
                repair = False
                repair_tp = 0
            nl, n = normalize_lot(lot, bal)
            if n:
                lot = nl
                bstep += n
                repair = False
                repair_tp = 0

        if pos is None:
            sig = i - 1
            d = signal(sig, b, c, I, lot, recovery)
            if not d:
                continue
            entry = z.o
            if not entry_ok(sig, entry, b, c, I, lot, recovery):
                rch += 1
                continue
            tpd = c.recovery_tp if recovery else TP
            sd = sl_dist(lot, c, recovery)
            pos = (d, entry, lot, tpd, sd, recovery)
            tr += 1
            if recovery:
                rent += 1

        d, en, L, tpd, sd, opened_rec = pos
        stop = en - d * sd
        target = en + d * tpd
        sh = z.l <= stop if d > 0 else z.h >= stop
        th = z.h >= target if d > 0 else z.l <= target

        # Conservative same-M5-bar ambiguity: SL first.
        if sh:
            bal -= L * sd
            minbal = min(minbal, bal)
            sl += 1
            when = z.dt
            pos = None
            dd = max(dd, (peak - bal) / peak if peak > 0 else 1.0)
            if bal <= 0:
                return R(False, True, 'BUST', bal, minbal, maxlot, L, tp, sl, rent, rtp,
                         tr, rch, bstep, dd*100, (z.ts-st)/86400, z.dt)
            if bal < BASE_BAL - 1e-9:
                lot = REC_LOT
                repair = False
                repair_tp = 0
                continue
            if repair:
                lot = round(max(BASE_LOT, L - STEP), 2)
                repair = False
                repair_tp = 0
            else:
                lot = L
                repair = True
                repair_tp = 0
            continue

        if th:
            bal += L * tpd
            peak = max(peak, bal)
            tp += 1
            when = z.dt
            pos = None
            if opened_rec:
                rtp += 1
                if bal >= BASE_BAL - 1e-9:
                    lot = BASE_LOT
                    repair = False
                    repair_tp = 0
                else:
                    lot = REC_LOT
                continue
            if L >= MILESTONE - 1e-9:
                return R(True, False, 'PASS_1LOT', bal, minbal, max(maxlot, L), L, tp, sl,
                         rent, rtp, tr, rch, bstep, dd*100, (z.ts-st)/86400, z.dt)
            if repair:
                if repair_tp == 0:
                    repair_tp = 1
                    lot = L
                else:
                    lot = round(L + STEP, 2)
                    repair = False
                    repair_tp = 0
            else:
                lot = round(L + STEP, 2)
            maxlot = max(maxlot, lot)
            continue

        adverse = max(0.0, en-z.l) if d > 0 else max(0.0, z.h-en)
        floating = bal - adverse * L
        dd = max(dd, (peak-floating)/peak if peak > 0 else 1.0)
        if floating <= 0:
            return R(False, True, 'BUST_FLOATING', bal, minbal, maxlot, L, tp, sl, rent,
                     rtp, tr, rch, bstep, dd*100, (z.ts-st)/86400, z.dt)

    return R(False, False, 'DATA_END', bal, minbal, maxlot, lot, tp, sl, rent, rtp, tr,
             rch, bstep, dd*100, (b[-1].ts-st)/86400, when)


def rank(a):
    return (
        sum(x.done for x in a),
        -sum(x.bust for x in a),
        min(x.max_lot for x in a),
        statistics.median(x.max_lot for x in a),
        statistics.median(x.balance for x in a),
        min(x.min_balance for x in a),
        sum(x.tp_count for x in a),
        -statistics.median(x.dd for x in a),
    )


def main():
    b = data.load()
    I = v21.prep(b)
    cal = v30.calibration_starts(b)
    cs = list(cfgs())
    print('=== BTC V36 MINIMAL ENTRY / DYNAMIC COMPOUND ===', flush=True)
    print('INDICATORS EMA20 EMA60 VWAP96 ATR only; price-action pullback/reclaim trigger; no composite score; no structure SL filter', flush=True)
    print('LOCKED TP300 exactPrevTP_SL noFixedMaxLot balanceFeasibility firstSLretry firstTPrepair secondTPadvance secondSLstepDown below20=0.01 noCooldown', flush=True)
    print(f'CAL_CONFIGS {len(cs)}', flush=True)
    best = None
    for n, c in enumerate(cs, 1):
        a = [run(b, s, c, I) for s in cal]
        rk = rank(a)
        if best is None or rk > best[0]:
            best = (rk, c, a)
        if n % 8 == 0 or n == len(cs):
            print(f'CAL_PROGRESS {n}/{len(cs)} best={best[0]} cfg={best[1]}', flush=True)
    rk, c, _ = best
    print('BEST_CFG', c, 'CAL_RANK', rk, flush=True)

    starts = v30.fresh_starts(b)
    a = [run(b, s, c, I) for s in starts]
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
        f'REJECT_CHASE={sum(r.reject_chase for r in a)} BALANCE_STEPS={sum(r.balance_steps for r in a)} BEST_CFG={c}',
        flush=True,
    )


if __name__ == '__main__':
    main()
