# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 16:00 UTC+7

Read `MASTER_TRADING_STATE.md`, then `SEPARATE_MARKET_RESEARCH_V1.md`, `CROSSMARKET_ROLLING_BLIND_V6.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, and `CRYPTO_SYMBOL_PROFILES_V1.md`.

## Immediate task
Continue improving Forex and Crypto separately toward TP/SL WR >=80% with average RR 1.0–1.5 using only honest held-out/walk-forward evidence. Current work uses **0 new market-data provider credits**.

## Mandatory architecture
- Forex and Crypto MUST NOT share one analysis method.
- Forex continues F8/V7 cross-currency factor/session/structure logic only.
- Crypto continues V24/Apr16 BTC+breadth+HTF+M15/M5 logic only, plus per-symbol linked-driver profiles.
- Every Crypto symbol has its own profile/context in `CRYPTO_SYMBOL_PROFILES_V1.md`; do not treat all coins as interchangeable.

## Forex current best
Broad benchmark: F8 = 20-day/560 forced signals, MARKET 50.72% WR, positive expectancy, RR around 1.42–1.45.

Selective candidate: **V7**.
Development May18–22: 26 trades, 80.77% WR, +0.945R, RR1.425.
Held-out validation May25–29: **29 trades, 18W/11L = 62.07% WR, +0.502R, RR1.407**.
This supersedes V5 selective candidate but does NOT meet 80% validation.

Rejected/supporting:
- V8 pair prior 52.94% -> reject.
- V9 nested pair walk-forward 61.54% / +0.492R / RR1.417 -> supporting, below V7.

## Crypto current best evidence
Canonical base remains V24/Apr16, not the newer weaker profile experiments.
- V24 validation: 42.75% WR, +0.132R, avg RR1.647, unstable across dates.
- Apr16 clean MARKET holdout: **51.92% WR, +0.350R**, direction 80% at 6h and 89.09% at 24h.

Per-symbol research:
- V28 family-profile validation 22.22% -> reject.
- V29 per-symbol conditional: development 76%; validation **43.75% / +0.094R / RR1.5 on 16 trades** -> research-only.
- V30 nested symbol walk-forward 33.33% / -0.167R -> reject.

Therefore keep V24/Apr16 structure and use symbol profiles as linked-driver context, not as a proven replacement score.

## Hourly managed-position interpretation
After MARKET/LIMIT fill, backtest should advance H+1/H+2/H+3... sequentially and decide HOLD/CUT using only information observable then. This is NOT an automation. CUT is separate from TP/SL WR, but CUT count/rate/R and total managed expectancy must be tracked.
Old committed data lack full H+1/H+2 snapshots for most trades; do not fabricate hourly cuts from future outcome/MFE/MAE.

## Promotion rule
Only say success when held-out/walk-forward evidence simultaneously has:
1. TP/SL WR >=80%;
2. RR 1.0–1.5;
3. positive expectancy including CUT;
4. non-trivial sample;
5. no future leakage.

**Current status: NOT YET ACHIEVED.**

## Latest files
- `docs/checkpoints/SEPARATE_MARKET_RESEARCH_V1.md`
- `docs/checkpoints/CRYPTO_SYMBOL_PROFILES_V1.md`
- `scripts/offline_forex_v7_separate.py`
- `scripts/offline_forex_v8_pair_prior.py`
- `scripts/offline_forex_v9_nested_pair.py`
- `scripts/offline_crypto_v28_separate.py`
- `scripts/offline_crypto_v29_symbol_conditional.py`
- `scripts/offline_crypto_v30_nested_symbol.py`

## New-chat instruction
`Tiếp tục Trading từ GitHub checkpoint mới nhất. Forex và Crypto phải nghiên cứu riêng. Forex selective best = V7 62.07% / +0.502R / RR1.407. Crypto giữ V24/Apr16 base; Apr16 MARKET 51.92%. Đọc CRYPTO_SYMBOL_PROFILES_V1.md để phân tích từng coin theo driver riêng. Mục tiêu 80% chưa đạt; không được giả vờ đã đạt.`
