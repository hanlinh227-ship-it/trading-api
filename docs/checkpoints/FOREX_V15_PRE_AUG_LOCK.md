# FOREX V15 — PRE-AUGUST LOCK

Locked: 2026-08-17 before any August Forex snapshot is fetched.

## Integrity
- Scanner universe: all 28 Forex pairs.
- Snapshot used for development/walk-forward: `data/provider_snapshots/forex_h1_feb_jul_2026.json` only.
- August data is NOT present in that snapshot and has NOT been evaluated by V15 at lock time.
- NO TRADE is allowed; every scan considers the full 28-pair universe.
- CUT is excluded from TP/SL WR but included in economic expectancy.

## Frozen execution
- mode: LIMIT
- planned RR: **1.0**
- structural SL with ATR floor: 0.65 ATR
- structure swing lookback: 6 hours
- max hold: 12 hours
- limit offset: 0.35 ATR
- limit expiry: 4 hours
- management review: H+2 onward
- CUT threshold: current R <= -0.45 AND hourly close breaks EMA20 against the thesis

## Frozen meta-label selector
- model: ExtraTrees
- max depth: 7
- min samples leaf: 25
- probability threshold: 0.70
- BUY-vs-SELL probability margin: 0.08
- portfolio: Top 1 qualifying setup per UTC day across all 28 pairs

## Pre-Aug expanding walk-forward
May 2026:
- 18 selected
- 12 TP / 2 SL / 4 CUT
- TP/SL WR 85.71%
- mean managed R +0.562

June 2026:
- 8 selected
- 6 TP / 0 SL / 2 CUT
- TP/SL WR 100.00%
- mean managed R +0.729

July 2026:
- 29 selected
- 17 TP / 5 SL / 7 CUT
- TP/SL WR 77.27%
- mean managed R +0.382

Combined May-Jul:
- **55 selected**
- **35 TP / 7 SL / 13 CUT**
- **TP/SL WR 83.33%**
- **mean managed R +0.491**
- CUT rate 23.64%
- 14 distinct pairs actually traded; all 28 were scanned.

## Promotion state
PRE-AUG TARGET PASSED. This is NOT final promotion. The parameters above are frozen before the untouched August test. If the untouched test is below target, this lock is rejected and must not be changed after seeing that holdout and then re-tested on the same holdout as if blind.
