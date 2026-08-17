# FOREX V15 — UNTOUCHED AUGUST FINAL1 PASS

Evaluated: 2026-08-17 after `FOREX_V15_PRE_AUG_LOCK.md` was committed.

## Integrity chain
1. V15 parameters were frozen in `docs/checkpoints/FOREX_V15_PRE_AUG_LOCK.md` before August Forex data was fetched.
2. The final snapshot was fetched afterward as `data/provider_snapshots/forex_h1_aug1_8_2026_final1.json`.
3. `scripts/eval_forex_v15_aug1_7_final1.py` trained only on pre-August events and applied the frozen execution/model unchanged to August 3–7.
4. All 28 Forex pairs were scanned at every eligible decision time; NO TRADE was allowed for non-qualified pairs.
5. CUT is excluded from TP/SL WR but remains included in managed expectancy.

## Frozen configuration
- execution: LIMIT
- planned RR: **1.0**
- structural SL + ATR floor: 0.65 ATR
- swing lookback: 6 hours
- max hold: 12 hours
- limit offset: 0.35 ATR
- limit expiry: 4 hours
- management review starts H+2
- management CUT: current R <= -0.45 AND hourly close breaks EMA20 against thesis
- model: ExtraTrees, depth 7, min leaf 25
- probability threshold: 0.70
- BUY-vs-SELL probability margin: 0.08
- top 1 qualifying setup per UTC day across the full 28-pair scan

## Untouched final holdout — 2026-08-03 through 2026-08-07
- final scan count: **840** pair/time scans
- candidate side-events after frozen execution geometry: 1,213
- selected trades: **5**
- TP: **5**
- SL: **0**
- CUT: **0**
- TP/SL WR: **100.00%**
- mean managed R including CUT: **+1.000R/trade**
- CUT rate: 0.00%
- planned RR: **1:1**

Selected outcomes:
- Aug 3 EURCHF SELL -> TP +1.000R
- Aug 4 EURAUD BUY -> TP +1.000R
- Aug 5 NZDCAD BUY -> TP +1.000R
- Aug 6 EURJPY SELL -> TP +1.000R
- Aug 7 CADJPY SELL -> TP +1.000R

## Status
**FOREX TARGET PASSED ON THE FIRST UNTOUCHED AUGUST HOLDOUT.**
The pass was not retroactively tuned. Do not modify V15 and re-label August 3–7 as blind.

GitHub Actions evidence:
- workflow: `Eval Forex V15 Aug3-7 Final1`
- run ID: `32019229044`
- evaluator reported `finalTargetMet: true`.
