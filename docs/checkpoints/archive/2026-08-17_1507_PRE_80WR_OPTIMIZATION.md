# PRE-80WR OPTIMIZATION ARCHIVE — 2026-08-17 15:07 UTC+7

This file is an explicit recovery marker before the zero-provider-credit optimization requested on 2026-08-17.

## Exact recovery commit
`de58e0a0ea2a6054b9c5839736be0efa80d01dce`

Git history at that commit is the authoritative full backup. Do not overwrite or reinterpret older evidence.

## Checkpoint blob SHAs at archive time
- `docs/checkpoints/MASTER_TRADING_STATE.md`: `ccdb23df601e70052f213d273745e9a386ea3f68`
- `docs/checkpoints/CURRENT_HANDOFF.md`: `39994c201b9a3f640fc4e88137d788fe1574b3f9`
- `docs/checkpoints/FOREX_STATE.md`: `91ae611a33d8afa66cdfaf7c70fb9aaa1adb56ab`
- `docs/checkpoints/CRYPTO_BREAKOUT_STATE.md`: `d201059742f08fa024f9dfd7ff9c8c6ff17b584d`

## Forex state before optimization
Frozen research baseline: F8.
Four consecutive frozen 5-day blocks, 560 forced signals / 20 trading days.
MARKET 489 resolved, 248 TP / 241 SL, WR 50.72%, weighted expectancy about +0.233R.
LIMIT 403 resolved, 169 TP / 234 SL, weighted expectancy about +0.246R.
Recommended execution 487 resolved, 247 TP / 240 SL, weighted expectancy about +0.237R.
Main unresolved weakness: common-factor/date-regime catastrophe risk, e.g. Jun04.

## Crypto state before optimization
No validated forced all-coin live engine.
V24 five-date June validation: 262 resolved, 112 TP / 150 SL, WR 42.75%, avg RR 1.647, +0.132R, highly unstable by date.
Apr16 MARKET-vs-LIMIT blind: MARKET 27 TP / 25 SL, WR 51.92%, +0.350R; LIMIT resolved fills WR 47.50%, avg effective RR 3.00R, +0.900R.
Known lesson: market regime/BTC/structure dominates symbol reputation; fixed LIMIT and forced-all-symbol trading are not robust live rules.

## Integrity rule for the next optimization
- Use only already committed result JSONs. No Twelve Data, exchange REST, or other provider calls.
- Report in-sample fitted ceiling separately from held-out/walk-forward results.
- A claimed >=80% WR is valid only if held-out/walk-forward and average planned/effective RR >=1.0 (prefer >=1.5), with non-trivial sample coverage.
- If 80% is only attainable by hindsight/cherry-picking, mark it REJECTED and do not promote it.
