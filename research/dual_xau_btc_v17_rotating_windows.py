#!/usr/bin/env python3
"""V17 rotating-window robustness harness for XAU + BTC.

Entry/exit logic is inherited from V16. The only structural change is validation:
every GitHub Actions run receives a different deterministic seed derived from
GITHUB_RUN_ID (or --seed when supplied), therefore every run samples a new set
of 10 historical start times.

The seed and exact start timestamps are printed so every result is reproducible.
Locked trading rules remain inherited from V16: $20 start, 0.02->1.00,
TP XAU +3 / BTC +300, no SL/cut/timeout, >=10-minute post-TP cooldown.
"""
from __future__ import annotations
import argparse, os, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_xau_btc_v16_entry_repair as v16
import dual_xau_btc_v14_joint as v14
import mt5_progressive_tp_backtest_v3 as x3
import mt5_progressive_tp_backtest_v8 as b8

TOP = 128
STAGE1 = 3


def resolve_seed(cli_seed: int | None) -> int:
    if cli_seed is not None:
        return cli_seed
    rid = os.getenv('GITHUB_RUN_ID')
    attempt = os.getenv('GITHUB_RUN_ATTEMPT', '1')
    if rid and rid.isdigit():
        return int(rid) * 100 + int(attempt)
    # Local fallback changes by invocation while remaining explicitly logged.
    import time
    return int(time.time_ns() % 2_147_483_647)


def rotating_starts(n: int, seed: int):
    # Keep starts inside first 78% so each window retains enough forward history.
    upper = max(10, int(n * .78))
    r = random.Random(seed)
    return sorted(r.sample(range(0, upper), 10))


def search(symbol: str, seed: int):
    if symbol == 'XAU':
        bars = x3.load(x3.DATA['XAUUSD']['url'])
        cs = list(v16.xcfgs())
        prep = v16.prep_xau
    else:
        bars = b8.load()
        cs = list(v16.bcfgs())
        prep = v16.prep_btc

    # Same workflow run uses the same seed for both symbols, but sampled timestamps
    # naturally differ because the datasets have different bar calendars.
    ss = rotating_starts(len(bars), seed)
    wins = [bars[s:] for s in ss]
    caches = [prep(w) for w in wins]

    print(f'=== {symbol} V17 ROTATING WINDOWS / V16 ENTRY CORE ===', flush=True)
    print('ROTATION_SEED', seed, flush=True)
    print('range', bars[0].dt, '->', bars[-1].dt, 'bars', len(bars), 'configs', len(cs), flush=True)
    print('starts', [bars[s].dt for s in ss], flush=True)

    stage = []
    for n, c in enumerate(cs, 1):
        rs = [v16.run_symbol(w, c, I, symbol) for w, I in zip(wins[:STAGE1], caches[:STAGE1])]
        sc = v14.score(rs)
        stage.append((sc, c, rs))
        if n % 500 == 0 or n == len(cs):
            print(f'PROGRESS {symbol} V17 stage1 {n}/{len(cs)} best={max(x[0][0] for x in stage)}/3', flush=True)

    surv = [x for x in stage if x[0][0] == 3]
    pool = surv if surv else sorted(stage, key=lambda x: x[0], reverse=True)[:TOP]
    if len(pool) > TOP:
        pool = sorted(pool, key=lambda x: x[0], reverse=True)[:TOP]
    print(f'{symbol} V17 SURVIVORS', len(surv), 'POOL', len(pool), flush=True)

    best = None
    for n, (sc, c, r3) in enumerate(pool, 1):
        rs = r3 + [v16.run_symbol(w, c, I, symbol) for w, I in zip(wins[3:], caches[3:])]
        full = v14.score(rs)
        if best is None or full > best[0]:
            best = (full, c, rs)
        if n % 10 == 0 or full[0] >= 6 or n == len(pool):
            print(f'PROGRESS {symbol} V17 stage2 {n}/{len(pool)} pass={full[0]}/10 sumTP={full[1]} alive={full[2]}/10', flush=True)
        if full[0] == 10:
            break

    sc, c, rs = best
    print(f'{symbol}_V17_BEST seed={seed} {c} pass={sc[0]}/10 sumTP={sc[1]} alive={sc[2]}/10', flush=True)
    for j, (s, r) in enumerate(zip(ss, rs), 1):
        print(f'{symbol}{j:02d} start={bars[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}', flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', choices=['XAU', 'BTC'], required=True)
    ap.add_argument('--seed', type=int, default=None)
    a = ap.parse_args()
    seed = resolve_seed(a.seed)
    return search(a.symbol, seed)


if __name__ == '__main__':
    sys.exit(main())