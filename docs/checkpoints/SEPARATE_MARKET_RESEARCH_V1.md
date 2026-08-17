# SEPARATE MARKET RESEARCH V1

Updated: 2026-08-17 UTC+7
Provider credits used in this round: **0**

## Mandatory architecture
Forex and Crypto MUST NOT share one research/entry methodology.

### Forex branch
Preserve F8/F7 lineage only:
- currency-factor coherence 3/6/12/24/72h;
- H1/H4 structure and EMA context;
- ADX/RSI/ATR minimal indicator roles;
- session state / impulse-vs-regime;
- pair archetype and common-factor/day risk;
- structural SL and realistic TP.
No BTC/breadth/crypto profile logic belongs in Forex.

### Crypto branch
Preserve V24/Apr16 lineage only:
- BTC state + whole-market breadth/regime;
- D1/H4/H1 structure + 6/24/72h momentum;
- M15/M5 path, anti-chase;
- fresh order flow only when available;
- continuation-MARKET vs structural pullback-LIMIT vs NO TRADE;
- symbol-specific linked-driver profiles from `CRYPTO_SYMBOL_PROFILES_V1.md`.
No Forex currency-factor/pair-archetype logic belongs in Crypto.

## Forex tests this round
### V7 separate factor/day-risk
Development May18-22:
- 26 trades, 21W/5L = 80.77% WR;
- +0.945R;
- avg RR 1.425.
Validation May25-29:
- 29 trades, 18W/11L = **62.07% WR**;
- **+0.502R**;
- **avg RR 1.407**.
This beats V5 (60.71%) and is the strongest selective Forex candidate currently found, but target 80% is NOT validated.

### V8 independent pair-prior
Validation 17 trades, 9W/8L = 52.94%, +0.275R, RR1.391. Rejected vs V7.

### V9 nested pair walk-forward
26 trades, 16W/10L = 61.54%, +0.492R, RR1.417. Valid chronological nested test but slightly below V7. Keep as supporting evidence, not replacement.

### Forex canonical state
- Broad comparator remains F8: 20-day/560-signal forced benchmark, 50.72% WR, positive expectancy.
- Selective candidate = **V7: 62.07% WR / +0.502R / RR1.407**.
- Do NOT claim Forex 80% is achieved. V7 development reached 80.77%, but held-out validation did not.

## Crypto tests this round
### Surviving base before this round
- V24 five-date validation: 42.75% WR, +0.132R, avg RR1.647; unstable by date.
- Apr16 clean MARKET holdout: **51.92% WR, +0.350R**, direction 80% at 6h and 89.09% at 24h.
These remain the strongest clean crypto evidence and must not be overwritten by weaker experiments.

### V28 profile-aware family weighting
Validation 18 trades, 4W/14L = 22.22%, -0.444R, RR1.5. Rejected.

### V29 per-symbol conditional Bayesian profile
Development: 25 trades, 19W/6L = 76.00%, +0.900R, RR1.5.
Validation: 16 trades, 7W/9L = **43.75% WR**, +0.094R, RR1.5.
Improved over V28 and turned expectancy positive, but sample <20 and below Apr16 clean MARKET WR. Research-only.

### V30 chronological nested symbol walk-forward
18 trades, 6W/12L = 33.33%, -0.167R, RR1.5. Rejected vs V29.

### Crypto canonical state
- Keep V24/Apr16 architecture as the base.
- Add per-symbol linked-driver profile as analysis context, NOT as a proven score replacement.
- Every symbol has a distinct profile in `CRYPTO_SYMBOL_PROFILES_V1.md`.
- Do NOT claim Crypto 80% is achieved.

## Hourly managed-position research
Desired mechanism remains: after MARKET/LIMIT fill, review sequentially H+1/H+2/H+3... using only information observable then, decision HOLD/CUT. CUT is separate from TP/SL WR.
Old committed Crypto data do not preserve full hourly snapshots. Forex has only coarse H+3 checkpoint evidence in some F8 records; it did not improve V5/V6. Never fabricate H+1/H+2 from future outcome/MFE/MAE.

## Target status
User target remains:
- TP/SL WR >=80%;
- average RR 1.0-1.5;
- positive managed expectancy including CUT;
- non-trivial sample;
- held-out/walk-forward integrity.

**NOT YET ACHIEVED.**
Best current valid selective Forex: 62.07% / RR1.407.
Best clean Crypto execution holdout: Apr16 MARKET 51.92% (original RR architecture); profile-specific V29 validation 43.75% / RR1.5 on only 16 trades.

Further threshold tuning on already revealed holdouts must not be called blind. With no new provider data allowed, future work should use only honest nested/cross-validation on committed data and preserve these baselines.

## New files
- `scripts/offline_forex_v7_separate.py`
- `.github/workflows/offline-forex-v7-separate.yml`
- `scripts/offline_forex_v8_pair_prior.py`
- `.github/workflows/offline-forex-v8-pair-prior.yml`
- `scripts/offline_forex_v9_nested_pair.py`
- `.github/workflows/offline-forex-v9-nested-pair.yml`
- `scripts/offline_crypto_v28_separate.py`
- `.github/workflows/offline-crypto-v28-separate.yml`
- `scripts/offline_crypto_v29_symbol_conditional.py`
- `.github/workflows/offline-crypto-v29-symbol-conditional.yml`
- `scripts/offline_crypto_v30_nested_symbol.py`
- `.github/workflows/offline-crypto-v30-nested-symbol.yml`
- `docs/checkpoints/CRYPTO_SYMBOL_PROFILES_V1.md`
