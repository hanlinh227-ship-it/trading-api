# MASTER TRADING STATE

Updated: 2026-08-17 16:00 UTC+7
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, then `SEPARATE_MARKET_RESEARCH_V1.md`, `CROSSMARKET_ROLLING_BLIND_V6.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, and the relevant market checkpoint.

## Mandatory separation
**Forex and Crypto MUST NOT share one research/entry methodology.**

### Forex lineage
Preserve F8/F7 only: cross-currency factor coherence, H1/H4 structure, session/impulse-vs-regime, minimal EMA20/50 + RSI14 + ATR14 + ADX14 roles, pair archetype/day common-factor risk, structural SL and realistic TP.

### Crypto lineage
Preserve V24/Apr16 only: BTC + market breadth/regime, D1/H4/H1 + 6/24/72h momentum, M15/M5 path/anti-chase, fresh order flow when available, continuation-MARKET vs structural pullback-LIMIT vs NO TRADE, and per-symbol linked-driver profiles.
Canonical symbol profile file: `docs/checkpoints/CRYPTO_SYMBOL_PROFILES_V1.md`.

## Universal integrity rules
- Never promote in-sample/lucky results as blind validation.
- Do not shrink TP merely to inflate WR.
- Structural invalidation determines SL first; ATR only buffers/normalizes.
- CUT is excluded from displayed TP/SL WR by user convention, but CUT count/rate/R and total managed expectancy must still be reported.
- Hourly HOLD/CUT is a BACKTEST mechanism: after fill, advance sequentially H+1/H+2/H+3... and use only observable information at that review time.
- Old committed data lack full H+1/H+2 snapshots for most trades; never invent hourly decisions from final outcome/MFE/MAE.
- Latest research rounds used **0 market-data provider credits**.

## Target
Promote only if genuinely held-out/walk-forward evidence reaches all:
- TP/SL WR >=80%;
- average planned/effective RR 1.0–1.5;
- positive expectancy including CUT;
- non-trivial sample;
- no future information leakage.

**Current status: target NOT achieved.**

# FOREX
## Broad comparator — F8
Four consecutive 5-day blocks / 560 forced signals:
- MARKET 489 resolved, 248 TP /241 SL = 50.72% WR;
- weighted expectancy ~+0.233R;
- typical RR ~1.42–1.45.
F8 remains the broad stress-test benchmark.

## Strongest selective candidate — V7
Forex V7 is fully separate from Crypto and continues F8/V5 logic.
Development May18–22:
- 26 trades, 21W/5L = 80.77% WR;
- +0.945R;
- avg RR 1.425.
Validation May25–29:
- **29 trades, 18W/11L = 62.07% WR**;
- **+0.502R**;
- **avg RR 1.407**.
V7 is the strongest selective Forex candidate currently found, but held-out validation is below 80%.

## Forex rejected/supporting variants
- V5 validation: 60.71% WR / +0.467R / RR1.403. Superseded by V7 selective candidate.
- V8 pair-prior: 52.94% / +0.275R / RR1.391. Rejected vs V7.
- V9 nested pair walk-forward: 61.54% / +0.492R / RR1.417. Supporting evidence, slightly below V7.
- V6 Top-K: 40% validation. Rejected.
- V4.1 daily-changing threshold: 36%. Rejected.

# CRYPTO
## Surviving base
Do not overwrite these with weaker experiments:
- V24 five-date validation: 42.75% WR, +0.132R, avg RR1.647; unstable by date.
- Apr16 clean MARKET holdout: **51.92% WR, +0.350R**, 6h direction 80%, 24h direction 89.09%.
- Fixed universal 0.35R LIMIT did not improve WR; execution value came from geometry/RR, not accuracy.

## Per-symbol requirement
Every researched coin must have its own linked-driver profile. Examples:
- ETH: BTC + ETH/BTC + staking/L2/ETF/protocol drivers;
- SOL: BTC + SOL/ETH + Solana DEX/meme/stablecoin/network drivers;
- LINK: DeFi/ETH + oracle/CCIP/RWA/staking;
- PENGU/memes: meme breadth + ecosystem/social/DEX flow + BTC/SOL/ETH beta as applicable;
- ONDO: RWA/Treasury-yield/institutional tokenization drivers;
- TAO/RENDER/VIRTUAL etc.: AI-sector breadth plus project-specific network/usage drivers.
Full 61-symbol map is in `CRYPTO_SYMBOL_PROFILES_V1.md`.

## Latest Crypto experiments
- V28 family-profile weighting: 22.22% validation / -0.444R / RR1.5. Rejected.
- V29 per-symbol conditional Bayesian profile: development 76%; validation **43.75% / +0.094R / RR1.5** on 16 trades. Research-only; below promotion sample and below Apr16 clean WR.
- V30 chronological nested symbol walk-forward: 33.33% / -0.167R / RR1.5. Rejected vs V29.
Therefore V24/Apr16 remains the canonical Crypto research base; symbol profiles are context layers, not yet a proven score replacement.

## Rejected Crypto logic — do not revive
- generic indicator stacking;
- V25 synchronized climax reversal;
- V26 macro-always-owns-direction;
- V27 assumption one completed M15 fixes bad state;
- extreme breadth alone as reversal/no-trade;
- universal fixed 0.35R LIMIT;
- static BUY/macro gate;
- static symbol reputation alone.

## Provider efficiency
Reuse committed data. Do not fetch new history unless explicitly allowed later. No recurring automation is part of the current backtest research.

## Handoff phrase
`Tiếp tục Trading từ GitHub checkpoint mới nhất. Đọc MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, SEPARATE_MARKET_RESEARCH_V1.md, TRADE_MANAGEMENT_HOURLY_V1.md và CRYPTO_SYMBOL_PROFILES_V1.md. Forex và Crypto là hai hệ hoàn toàn riêng. Forex selective tốt nhất hiện tại V7 = 62.07% WR / +0.502R / RR1.407. Crypto giữ V24/Apr16 làm base; Apr16 MARKET = 51.92% WR. Mục tiêu 80% chưa đạt.`
