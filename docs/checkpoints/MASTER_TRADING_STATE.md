# MASTER TRADING STATE

Updated: 2026-08-17 16:31 UTC+7
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, then `ITERATIVE_80WR_RESEARCH_V2.md`, `SEPARATE_MARKET_RESEARCH_V1.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, `CRYPTO_SYMBOL_PROFILES_V1.md`, and the relevant market checkpoint.

## Mandatory separation
**Forex and Crypto MUST NOT share one research/entry methodology.**

### Forex lineage
Preserve F8/V7 only: cross-currency factor coherence, H1/H4 structure, session/impulse-vs-regime, minimal EMA20/50 + RSI14 + ATR14 + ADX14 roles, pair archetype/day common-factor risk, structural SL and realistic TP. No BTC/breadth/crypto profile logic.

### Crypto lineage
Preserve V24/Apr16 only: BTC + market breadth/regime, D1/H4/H1 + 6/24/72h momentum, M15/M5 path/anti-chase, fresh order flow when actually available, continuation-MARKET vs structural pullback-LIMIT vs NO TRADE, and per-symbol linked-driver profiles. No Forex currency-factor/pair-archetype logic.
Canonical symbol profile file: `docs/checkpoints/CRYPTO_SYMBOL_PROFILES_V1.md`.

## Universal integrity rules
- Never promote in-sample/lucky results as blind validation.
- Once a validation block is revealed, do not retune against it and call the result blind again.
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

**Current global status: target NOT achieved.**

# FOREX
## Broad comparator — F8
Four consecutive 5-day blocks / 560 forced signals:
- MARKET 489 resolved, 248 TP /241 SL = 50.72% WR;
- weighted expectancy ~+0.233R;
- typical RR ~1.42–1.45.
F8 remains the broad stress-test comparator.

## Strongest selective candidate — V7
Development May18–22:
- 26 trades, 21W/5L = 80.77% WR;
- +0.945R;
- avg RR 1.425.
Held-out validation May25–29:
- **29 trades, 18W/11L = 62.07% WR**;
- **+0.502R**;
- **avg RR 1.407**.
V7 remains the strongest non-trivial selective Forex held-out candidate.

## Latest iterative Forex results
Canonical details: `ITERATIVE_80WR_RESEARCH_V2.md`.
- V10 nonlinear ML walk-forward: 57.89%; coarse H+3 management 61.11% with one CUT. Reject vs V7.
- V11 day-regime gate: **64.71% / +0.563R / RR1.412**, but only 17 trades; supporting, not promoted.
- V12 legacy F4 path gate: 27.91% external validation; reject.
- V13 genuine H+3/H+6/H+12 management: 0 CUTs; validation stayed 62.07%; no improvement.
- V14 independent BUY/SELL: BUY development 88.24% but validation 53.33%; SELL disabled; reject as overfit.
- F11 Jun08–12 is aggregate/day-level only; per-day MARKET WR ranged from 65.38% down to 34.62%, insufficient to validate an 80% selective rule without per-trade features.

## Forex integrity boundary
No genuinely untouched, feature-complete per-trade Forex block remains in the committed repository for a new selective-entry validation. Further tuning May outcomes is development-only. A new 80% claim requires a new frozen hypothesis followed by a new untouched block.

# CRYPTO
## Surviving base
Do not overwrite these with weaker experiments:
- V24 five-date validation: 42.75% WR, +0.132R, original avg RR1.647; unstable by date.
- Apr16 clean MARKET holdout: **51.92% WR, +0.350R**, 6h direction 80%, 24h direction 89.09%.
- Fixed universal 0.35R LIMIT did not improve WR; execution value came from geometry/RR, not accuracy.

## Parser correction — mandatory
The generic `extract_crypto()` lineage used in several newer profile experiments did not consistently inherit parent/day `priceBreadth`, `flowBreadth`, `flowCoverage`, and `marketRegime` into child trades. Correct recursive context inheritance is modeled after `scripts/offline_crypto_regime_optimizer_v3_fast.py`.

Therefore V28–V33 must NOT be used as canonical promotion evidence where they depend on that old parser/context. Preserve them as lineage only. V24/Apr16 remain clean base evidence; V35 was rebuilt with corrected inheritance.

## Per-symbol requirement
Every researched coin must have its own linked-driver profile. Full 61-symbol map: `CRYPTO_SYMBOL_PROFILES_V1.md`. Generic RSI/EMA scoring must not replace symbol-specific context.

## Latest clean Crypto results
### V34 fresh-flow mode
Earlier Jul02 development; frozen on later Jul04.
- Jul04 filtered validation: **37 trades, 29W/8L = 78.38% WR, +0.959R, RR1.5**.
Promising, below 80 and only one later date.

### V34C focused fresh-flow mode
Rule selected solely on Jul02 from pre-entry OFI/score/HTF/relative-strength/micro/breadth/BTC fields; frozen on Jul04.
- Jul02 selected dev: 10 trades, 70.00%, +0.750R, RR1.5.
- Jul04 frozen validation: **24 trades, 19W/5L = 79.17% WR, +0.979R, RR1.5**.
This is the closest clean Crypto result to target. It still misses 80% and Jul04 is now revealed, so further tuning against Jul04 cannot be called blind.

### V35 corrected profile/regime walk-forward
- 640 recovered rows / 12 dates, baseline35.78% under conservative RR cap1.5;
- expanding selected WF: 28 trades, 8W/20L = 28.57%, -0.286R, RR1.5.
Reject as replacement for V24/Apr16.

## Crypto operational split
1. `FLOW_AVAILABLE`: keep V24/V34/V34C lineage; genuine fresh flow is valuable and produced the best new result (79.17% one-day validation).
2. `FLOW_MISSING`: keep conservative BTC+breadth/regime + HTF + M15/M5 + symbol-specific drivers + NO TRADE. Current stored features do not validate an 80% selector.

## Crypto integrity boundary
The 12 corrected old dates and Jul02/Jul04 flow samples are now revealed. Further retuning them is diagnostic/development only. A global 80% promotion requires new untouched feature-complete dates after the next hypothesis is frozen.

# Rolling managed-position architecture
Desired mechanism remains H+1/H+2/H+3... HOLD/CUT using only information observable then.
- Crypto old rows do not contain full hourly snapshots.
- Forex V13 honestly tested available H+3/H+6/H+12 checkpoints and found zero useful CUTs in its held validation sample.
- Never derive CUT from final MFE/MAE/outcome.

## Provider efficiency
This iterative round used **0 provider credits**. Reuse committed data. Do not fetch new history unless explicitly allowed later.

## Handoff phrase
`Tiếp tục Trading từ GitHub checkpoint mới nhất. Đọc MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md và ITERATIVE_80WR_RESEARCH_V2.md trước. Forex/Crypto là hai hệ riêng. Forex best nontrivial held-out = V7 62.07% / +0.502R / RR1.407; V11 64.71% nhưng n=17. Crypto clean FLOW_AVAILABLE best = V34C Jul04 79.17% / +0.979R / RR1.5 trên 24 lệnh, nhưng chỉ một validation date và vẫn dưới 80. V28–V33 generic-parser results không được dùng để promote. Không được nói 80% đã đạt.`
