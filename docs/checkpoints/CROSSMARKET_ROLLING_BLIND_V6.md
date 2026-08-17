# CROSS-MARKET ROLLING BLIND V6 CHECKPOINT

Updated: 2026-08-17 15:45 UTC+7
Provider credits used in this research round: **0**

## User objective
Improve Forex + Crypto entry quality using only already committed historical/blind data, with a target of:
- TP/SL win rate >= 80%;
- planned/effective RR between 1.0 and 1.5;
- after fill, rolling position management that re-evaluates the trade and decides HOLD/CUT using only information observable at that review time;
- CUT is reported separately and excluded from TP/SL win rate, but managed expectancy including CUT must also be reported.

## Correct rolling-blind interpretation
For a filled MARKET or LIMIT order:
1. freeze entry/SL/TP at fill;
2. advance the historical clock sequentially;
3. at each review point use only information known up to that point;
4. decide HOLD or CUT;
5. never inspect later candles before an earlier HOLD/CUT decision.

The desired live/research design is H+1, H+2, H+3... hourly. Existing committed historical result JSONs do not contain full hourly snapshots for all trades. Therefore no fake H+1/H+2 replay is allowed.

## Available management replay
Forex F8-style trade records preserve `market.bars` and direction closes at 3h/6h/12h/24h. This allowed a genuine H+3 management proxy:
- if TP/SL occurred before H+3, final outcome remains unchanged;
- if trade survived beyond H+3, only the H+3 observable close may be used for the H+3 HOLD/CUT rule.
Crypto historical records do not preserve an equivalent replayable hourly/checkpoint path in the committed dataset.

## RR remapping rule
To compare with requested RR 1.0–1.5 without inventing future paths:
- trades with original RR <1.0 are excluded;
- original RR >1.5 is conservatively capped to 1.5;
- an original TP at RR>1.5 remains a TP at 1.5 because price necessarily crossed 1.5R first;
- an original SL is NEVER converted to TP without path evidence, even though a nearer 1.5R target might theoretically have been reached first.
This biases the remap conservatively rather than manufacturing winners.

# V4.1 — rolling walk-forward entry selector
Workflow run: `32011504773`

Forex recovered:
- 238 resolved trade records / 10 dates;
- baseline 119W /119L = 50.00% WR;
- mean +0.217R;
- avg original RR 1.447.

Daily changing walk-forward entry rule FAILED:
- 25 selected trades /5 dates;
- 9W /16L = 36.00% WR;
- -0.142R;
- avg RR 1.438.

Forex best direct in-sample gate (diagnostic only):
- 48 trades /10 dates;
- 29W /19L = 60.42% WR;
- +0.481R;
- avg RR 1.441.

Crypto recovered:
- 640 trades /12 dates;
- 229W /411L = 35.78% WR;
- avg RR 1.639 before cap.
Daily changing selector collapsed to 7.69% WR on its selected walk-forward sample. Rejected.

Conclusion: choosing a new threshold rule every day is unstable/overfit.

# V5 — one frozen rule, chronological development -> validation
Workflow successful run: `32011669871`

## FOREX V5 — strongest new valid result
Development: 2026-05-18 through 2026-05-22.
Validation: 2026-05-25 through 2026-05-29.

Frozen entry rule selected on development only:
- group ANY;
- mode ANY;
- BUY only;
- score >=1;
- ADX >=20;
- no coh3 minimum;
- impulseEvidence >=3;
- no dev-distance cap;
- H1 aligned with trade side.

Development:
- 31 trades;
- 23W /8L = 74.19% WR;
- +0.794R;
- avg capped RR 1.437;
- positive-day rate 100%.

Untouched validation:
- 28 trades;
- 17W /11L = **60.71% WR**;
- **+0.467R**;
- **avg RR 1.403**;
- median day WR 61.12%;
- positive-day rate 75%.

This is a legitimate improvement over the 50% recovered baseline sample, but it does NOT reach 80%.

H+3 CUT proxy chosen on development: threshold -0.4R.
It made zero CUTs in both development and validation because selected trades either resolved before H+3 or never met the threshold while alive. Therefore management did not improve V5 validation; result stayed 60.71%.

Important: this does NOT disprove hourly H+1/H+2 management. It only says the coarse H+3 proxy available in the old data added no value for this selected sample.

## CRYPTO V5
Development: first six recovered dates through 2026-05-27.
Validation: 2026-05-30, 06-18, 06-21, 06-24, 06-27, 06-30.

Frozen rule from development:
- BUY only;
- |macroScore| >=4;
- other gates open.

Development after conservative 1.5R cap:
- 57 trades;
- 32W /25L = 56.14% WR;
- +0.404R;
- avg RR 1.5.

Validation:
- 31 trades;
- 6W /25L = **19.35% WR**;
- -0.516R;
- avg RR 1.5.

Rejected. Static BUY/macro ownership does not generalize across Crypto regimes.

# V6 — frozen confidence score + daily Top-K
Workflow run: `32011803613`

## Forex
Frozen on first half: FAST confidence, Top 5/day.
Development:
- 25 trades;
- 60.00% WR;
- +0.500R;
- RR 1.5.
Validation:
- 25 trades;
- 10W /15L = 40.00% WR;
- 0.000R;
- RR 1.5.
H+3 CUT rule produced zero CUTs. Rejected vs V5.

## Crypto
Frozen on first half: RAW confidence, Top 8/day.
Development:
- 48 trades;
- 36W /12L = 75.00% WR;
- +0.875R;
- RR 1.5.
Validation:
- 48 trades;
- 18W /30L = 37.50% WR;
- -0.062R;
- RR 1.5.
Rejected. The 75% development result did not generalize.

# Current conclusions
1. Target 80% WR + RR 1.0–1.5 is **NOT validated** on existing committed data.
2. Best new valid entry improvement from this round is Forex V5: **60.71% WR, +0.467R, RR 1.403** on untouched validation.
3. Do not replace canonical forced-all-pair F8 research baseline with V5; V5 is a selective live-entry candidate, while F8 remains the broad benchmark.
4. Crypto does not support a stable static entry gate from the stored features. BTC/breadth/regime/current structure must dominate; static symbol/macro reputation is rejected.
5. Full hourly H+1/H+2/H+3... management cannot be honestly replayed on old Crypto data or all old Forex blocks because those hourly snapshots were not committed.
6. Do not fabricate hourly HOLD/CUT from final MFE/MAE or final outcome.
7. Future research capture should store hourly state snapshots so the exact desired management engine can be blind-tested later.

## Files created this round
- `scripts/offline_crossmarket_rolling_blind_v4.py`
- `.github/workflows/offline-crossmarket-rolling-blind-v4.yml`
- `scripts/offline_crossmarket_fixed_rule_v5.py`
- `.github/workflows/offline-crossmarket-fixed-rule-v5.yml`
- `scripts/offline_crossmarket_topk_v6.py`
- `.github/workflows/offline-crossmarket-topk-v6.yml`

## Cross-chat rule
Read this file after `MASTER_TRADING_STATE.md` and `CURRENT_HANDOFF.md`. Do not claim 80% is achieved. Preserve Forex F8 as the broad baseline and V5 as the strongest selective-entry candidate found in this round. Full hourly management remains a protocol awaiting replayable H+1/H+2 snapshots.
