# CRYPTO V36B — UNTOUCHED AUGUST FINAL1 PASS

Evaluated: 2026-08-17 after `CRYPTO_V36B_PRE_AUG_LOCK.md` was committed.

## Integrity chain
1. V36b parameters were frozen in `docs/checkpoints/CRYPTO_V36B_PRE_AUG_LOCK.md` before August data was fetched.
2. The final snapshot was then fetched separately as `data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json`.
3. The evaluator `scripts/eval_crypto_v36b_aug1_7_final1.py` retrained only on pre-August rows and applied the frozen execution/model parameters unchanged to August 1–7.
4. All 61 configured symbols were loaded; every eligible 4H scan checked the full universe. NO TRADE was allowed.
5. CUT is excluded from displayed TP/SL WR but included in managed R.

## Frozen configuration
- execution: LIMIT
- planned RR: **1.0**
- risk floor: 0.65 ATR + structural swing invalidation
- swing lookback: 5 x 4H bars
- max hold: 4 x 4H bars
- limit offset: 0.70 ATR
- limit expiry: 1 x 4H bar
- model: HistGradientBoosting, depth 3, leaf 8
- threshold: 0.66
- BUY-vs-SELL probability margin: 0.16
- top 1 qualifying setup per UTC day

## Untouched final holdout — 2026-08-01 through 2026-08-07
- requested scan slots: 2,562 = 61 symbols x 42 4H decision timestamps
- eligible scan slots: 2,562
- selected trades: **7**
- TP: **4**
- SL: **1**
- CUT: **2**
- TP/SL WR: **80.00%**
- mean managed R including CUT: **+0.657R/trade**
- average CUT R: **+0.798R**
- CUT rate: 28.57%
- planned RR: **1:1**

Selected outcomes:
- Aug 1 STX BUY -> CUT +0.965R
- Aug 2 LDO SELL -> CUT +0.630R
- Aug 3 ADA BUY -> TP +1.000R
- Aug 4 WLD SELL -> TP +1.000R
- Aug 5 KAITO SELL -> TP +1.000R
- Aug 6 JTO BUY -> TP +1.000R
- Aug 7 HYPE SELL -> SL -1.000R

## Status
**CRYPTO TARGET PASSED ON THE FIRST UNTOUCHED AUGUST HOLDOUT.**
This pass is not retroactively tuned. Do not modify V36b and re-label Aug 1–7 as blind. The remaining later August period stays available for future confirmation if desired.

GitHub Actions evidence:
- workflow: `Eval Crypto V36b Aug1-7 Final1`
- run ID: `32019086571`
- evaluator reported `finalTargetMet: true`.
