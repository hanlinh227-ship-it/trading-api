# FOREX META V1 — OFFLINE CHECKPOINT

Updated: 2026-08-17 UTC+7

## Purpose
Fast improvement/retest using only committed Forex result JSONs. No Twelve Data/API calls are allowed in this stage.

## Inputs
- data/blind_backtest_forex_f4.json
- data/blind_backtest_forex_f5_horizon.json
- data/blind_backtest_forex_f6.json
- data/blind_backtest_forex_f6_dual_horizon.json
- generated meta: data/offline_forex_meta_v1.json

Provider credits used by meta stage: 0.

## Aggregate evidence
Across the representative forced blocks selected by the offline meta analyzer:
- MARKET mean resolved WR: 38.23%
- MARKET mean expectancy: -0.067R
- LIMIT mean resolved WR: 28.99%
- LIMIT mean expectancy: -0.096R

Conclusion: there is not yet one universal forced-all-pair Forex method that is robust enough. F5's +0.015R block was not stable across other blocks. F6 dual-horizon hard classification is rejected as a default upgrade because its blind block returned 38.6% MARKET WR and -0.119R.

## Robust pair evidence across four canonical result blocks
ROBUST_POSITIVE by the conservative offline meta grade:
- EURAUD
- USDJPY
- GBPAUD
- USDCHF
- AUDCHF
- GBPUSD
- NZDCAD
- GBPNZD

WATCH_POSITIVE:
- CADCHF
- USDCAD
- EURUSD
- AUDJPY

WEAK_REWORK:
- AUDNZD
- AUDUSD
- CADJPY
- EURCAD
- EURNZD
- GBPCAD
- GBPJPY
- NZDCHF
- NZDJPY
- NZDUSD

MIXED:
- AUDCAD
- CHFJPY
- EURCHF
- EURGBP
- EURJPY
- GBPCHF

Do not interpret these grades as live permission to trade or skip a pair. They are research diagnostics from small blocks and must guide pair/archetype redesign.

## Strong examples
- EURAUD: 4/4 positive-expectancy blocks, median expectancy +0.656R, mean WR 68.75%.
- USDJPY: 4/4 positive blocks, median expectancy +0.660R, mean WR 62.50%, mean direction accuracy 68%.
- GBPUSD: 3/4 positive blocks, median expectancy +0.218R, mean WR 53.75%, 24h direction evidence stronger than 3h.
- CADCHF: only 2/4 positive but direction evidence is strong; mean 3h direction ~90%, so execution/barrier deserves investigation before bias is discarded.

## Core method retained
Do NOT add more indicators.
Keep:
- EMA20/50 = structure/value/slope
- RSI14 = exhaustion only
- ATR14 = volatility/risk normalization
- ADX14 = trend/chop regime
- full-network cross-currency strength

## Improvements now required
1. Shared core + conservative archetype/pair adaptation; no 28 unrelated models.
2. Horizon is evidence, not a hard two-class switch. F6 dual-horizon hard classification underperformed.
3. MARKET remains default for fresh impulse/continuation.
4. LIMIT only when a real structural/value pullback exists; never as universal RR optimizer.
5. Separate bias failure from barrier/path failure (`SL but later direction correct` vs `SL and direction wrong`).
6. Do not manufacture WR using tiny TP. Review direction + expectancy + RR together.
7. Weak-pair redesign should focus first on AUDUSD, GBPJPY, NZDUSD/NZDJPY/NZDCHF, CADJPY, EURCAD/GBPCAD.
8. Strong-pair behavior should be studied for transferable archetype rules, not copied blindly.

## Zero-credit research rule
Before any new Twelve Data historical fetch, use committed outputs for offline diagnostics and replay. A new paid/provider-data blind block is justified only after a candidate rule is frozen and has beaten current baselines in offline cross-block diagnostics without cherry-picking.

## Current interpretation
The biggest remaining problem is directional/regime classification at pair level, not indicator quantity. MARKET/LIMIT and TP/SL are secondary once bias quality is improved.
