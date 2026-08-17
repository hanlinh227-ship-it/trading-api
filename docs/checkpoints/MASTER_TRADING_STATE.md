# MASTER TRADING STATE

Updated: 2026-08-17 UTC+7
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, `FOREX_V15_PRE_AUG_LOCK.md`, `FOREX_V15_FINAL1_PASS.md`, `CRYPTO_V36B_PRE_AUG_LOCK.md`, `CRYPTO_V36B_FINAL1_PASS.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, and `CRYPTO_SYMBOL_PROFILES_V1.md`.

## Mandatory separation
**Forex and Crypto remain two separate research/entry systems.** Do not mix Forex currency-factor features into Crypto or Crypto BTC/breadth features into Forex.

## Universal accounting/integrity rules
- Scanner must evaluate the full configured universe; NO TRADE is allowed and expected for non-qualified symbols.
- Displayed win rate is `TP / (TP + SL)`.
- CUT is excluded from displayed TP/SL WR by user convention, but CUT count/rate/R and managed expectancy including CUT are mandatory.
- Initial planned RR must be exactly 1.0 or 1.5 for the promoted systems.
- Structural invalidation determines SL; ATR is a floor/buffer, not a substitute for structure.
- Never retune an exposed final holdout and relabel it blind.
- Final selector parameters must be locked before final-holdout data is fetched.
- Backtest success is not a guarantee of identical live/future WR.

# RESEARCH TARGET STATUS
Requested target:
- scan all 28 Forex pairs and all 61 Crypto symbols;
- selective MARKET/LIMIT/NO TRADE allowed;
- TP/SL WR >=80%;
- planned RR 1:1 or 1:1.5;
- positive managed expectancy including CUT;
- no future leakage;
- pass a new untouched holdout after parameters are frozen.

**Current research status: TARGET ACHIEVED.**
Canonical machine-readable record: `data/final_target_80wr_validation_2026-08-17.json`.

# FOREX — PROMOTED V15
## Data/integrity chain
- New H1 research snapshot: `data/provider_snapshots/forex_h1_feb_jul_2026.json`.
- Coverage: all 28 configured Forex pairs.
- V15 was optimized/walk-forward tested only on pre-August data.
- Frozen before August in `FOREX_V15_PRE_AUG_LOCK.md`.
- Untouched final snapshot fetched afterward: `data/provider_snapshots/forex_h1_aug1_8_2026_final1.json`.
- Final evaluator: `scripts/eval_forex_v15_aug1_7_final1.py`.
- GitHub Actions final run: `32019229044`.

## Frozen V15 method
Forex-specific context:
- cross-currency factor state from 3h/6h/12h/24h/72h returns;
- currency coherence/rank separation;
- H1 + completed H4 structure;
- ADX/RSI, session path, EMA distance;
- independent BUY/SELL hypotheses;
- ExtraTrees meta-label selects TAKE vs NO TRADE and direction;
- top 1 qualifying setup per UTC day across the full 28-pair scan.

Execution:
- LIMIT;
- planned RR **1:1**;
- structural swing lookback 6h;
- ATR risk floor 0.65;
- limit offset 0.35 ATR;
- limit expiry 4h;
- max hold 12h;
- from H+2, CUT only if current R <= -0.45 and hourly close breaks EMA20 against thesis.

Selector:
- ExtraTrees depth 7;
- min leaf 25;
- probability threshold 0.70;
- BUY-vs-SELL probability margin 0.08;
- Top 1/day.

## Pre-Aug expanding walk-forward
May:
- 18 selected;
- 12 TP / 2 SL / 4 CUT;
- TP/SL WR 85.71%;
- mean managed R +0.562.

June:
- 8 selected;
- 6 TP / 0 SL / 2 CUT;
- TP/SL WR 100.00%;
- mean managed R +0.729.

July:
- 29 selected;
- 17 TP / 5 SL / 7 CUT;
- TP/SL WR 77.27%;
- mean managed R +0.382.

Combined May-Jul:
- **55 selected**;
- **35 TP / 7 SL / 13 CUT**;
- **TP/SL WR 83.33%**;
- **mean managed R +0.491**;
- CUT rate 23.64%;
- 14 pairs actually traded; all 28 were scanned.

## Untouched August Final1
Signal dates: 2026-08-03 through 2026-08-07.
- **840 pair/time scans** across all 28 pairs;
- **5 selected**;
- **5 TP / 0 SL / 0 CUT**;
- **TP/SL WR 100.00%**;
- **mean managed R +1.000R/trade**;
- planned RR **1:1**;
- `finalTargetMet: true`.

Final trades:
- Aug03 EURCHF SELL -> TP;
- Aug04 EURAUD BUY -> TP;
- Aug05 NZDCAD BUY -> TP;
- Aug06 EURJPY SELL -> TP;
- Aug07 CADJPY SELL -> TP.

**Forex V15 is the promoted selective research scanner.** Preserve F8/V7 only as historical comparators, not current promoted systems.

# CRYPTO — PROMOTED V36b
## Data/integrity chain
- New 4H snapshot: `data/provider_snapshots/crypto_4h_feb_jul_2026.json`.
- Coverage: **61/61** configured symbols.
- Sources: OKX 57, Gate 2, Kraken 2.
- V36b corrected warm-up eligibility so newly listed coins cannot become candidates before every required indicator exists.
- Frozen before August in `CRYPTO_V36B_PRE_AUG_LOCK.md`.
- Untouched final snapshot fetched afterward: `data/provider_snapshots/crypto_4h_aug1_8_2026_final1.json`.
- Final evaluator: `scripts/eval_crypto_v36b_aug1_7_final1.py`.
- GitHub Actions final run: `32019086571`.

## Frozen V36b method
Crypto-specific context:
- BTC 24h/72h regime;
- full-market breadth and cross-sectional dispersion;
- 24h/72h relative strength vs BTC;
- H4 + completed D1 structure;
- ADX/RSI/EMA path and momentum;
- 61 symbol identities + linked-driver family context;
- HistGradientBoosting meta-label selects TAKE vs NO TRADE and direction;
- top 1 qualifying setup per UTC day across the full 61-symbol scan.

Execution:
- LIMIT;
- planned RR **1:1**;
- structural swing lookback 5 x 4H bars;
- ATR risk floor 0.65;
- limit offset 0.70 ATR;
- limit expiry 1 x 4H bar;
- max hold 4 x 4H bars;
- no early management CUT in this frozen candidate; unresolved positions become timeout CUT.

Selector:
- HistGradientBoosting depth 3;
- min leaf 8;
- probability threshold 0.66;
- BUY-vs-SELL probability margin 0.16;
- Top 1/day.

## Pre-Aug expanding walk-forward
May:
- 31 selected;
- 22 TP / 6 SL / 3 CUT;
- TP/SL WR 78.57%;
- mean managed R +0.499.

June:
- 30 selected;
- 23 TP / 5 SL / 2 CUT;
- TP/SL WR 82.14%;
- mean managed R +0.586.

July:
- 31 selected;
- 21 TP / 4 SL / 6 CUT;
- TP/SL WR 84.00%;
- mean managed R +0.576.

Combined May-Jul:
- **92 selected**;
- **66 TP / 15 SL / 11 CUT**;
- **TP/SL WR 81.48%**;
- **mean managed R +0.553**;
- CUT rate 11.96%;
- 40 symbols actually traded; all 61 were loaded/scanned.

## Untouched August Final1
Signal dates: 2026-08-01 through 2026-08-07.
- requested scan slots: **2,562**;
- eligible scan slots: **2,562**;
- **7 selected**;
- **4 TP / 1 SL / 2 CUT**;
- **TP/SL WR 80.00%**;
- **mean managed R +0.657R/trade** including CUT;
- average CUT R +0.798R;
- CUT rate 28.57%;
- planned RR **1:1**;
- `finalTargetMet: true`.

Final outcomes:
- Aug01 STX BUY -> CUT +0.965R;
- Aug02 LDO SELL -> CUT +0.630R;
- Aug03 ADA BUY -> TP;
- Aug04 WLD SELL -> TP;
- Aug05 KAITO SELL -> TP;
- Aug06 JTO BUY -> TP;
- Aug07 HYPE SELL -> SL.

**Crypto V36b is the promoted selective research scanner.** Preserve V24/Apr16/V34C only as historical comparators.

# Live/forward interpretation
Promotion means the backtest/research target was achieved under the stated selective full-universe scan protocol. It does NOT mean every individual symbol independently has an 80% WR, nor that future/live WR is guaranteed.

Live operation must still:
- refresh exact current price before issuing any signal;
- apply point-in-time news/economic-calendar/event context as an additional live safety layer;
- use MARKET/LIMIT/NO TRADE according to current geometry;
- after fill, review open trades with current price/structure/news and record HOLD/CUT decisions without hindsight;
- preserve CUT accounting separately from TP/SL WR.

## Provider efficiency
- Crypto Feb-Jul and August final snapshots used public exchange endpoints and are now frozen in-repo.
- Forex Feb-Jul and August final snapshots used Twelve Data only for snapshot collection; optimization/evaluation after snapshots were frozen ran offline without repeated provider calls.

## Handoff phrase
`Tiếp tục Trading từ GitHub checkpoint mới nhất. Research target 80% đã đạt theo selective full-universe scanner protocol. Forex promoted = V15, scans 28/28, RR1:1, pre-Aug 83.33% on 55 selected, untouched Aug03-07 = 5TP/0SL =100%. Crypto promoted = V36b, loads/scans 61/61, RR1:1, pre-Aug 81.48% on92 selected, untouched Aug01-07 =4TP/1SL/2CUT =80% TP/SL WR, +0.657R incl CUT. Đọc FOREX_V15_PRE_AUG_LOCK.md, FOREX_V15_FINAL1_PASS.md, CRYPTO_V36B_PRE_AUG_LOCK.md, CRYPTO_V36B_FINAL1_PASS.md và data/final_target_80wr_validation_2026-08-17.json. Không retune final holdouts.`
