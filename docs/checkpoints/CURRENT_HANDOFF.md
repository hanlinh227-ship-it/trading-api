# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 16:31 UTC+7

Read `MASTER_TRADING_STATE.md`, then `ITERATIVE_80WR_RESEARCH_V2.md`, `SEPARATE_MARKET_RESEARCH_V1.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, and `CRYPTO_SYMBOL_PROFILES_V1.md`.

## Immediate task
Continue Forex and Crypto as separate systems. Do not retune already revealed validation blocks and present them as new blind evidence. This research round used **0 new market-data provider credits**.

## Target
Only promote when genuinely held-out/walk-forward evidence simultaneously reaches:
1. TP/SL WR >=80%;
2. average RR 1.0–1.5;
3. positive expectancy including CUT;
4. non-trivial sample;
5. no future leakage.

**Current global status: NOT ACHIEVED.**

# Forex
Broad comparator: F8 20-day/560 forced signals, MARKET 50.72% WR, positive expectancy, RR around1.42–1.45.

Strongest non-trivial selective held-out candidate remains **V7**:
- development May18–22: 26 trades, 80.77%, +0.945R, RR1.425;
- held validation May25–29: **29 trades, 18W/11L = 62.07%, +0.502R, RR1.407**.

Latest attempts:
- V10 ML:57.89%; H+3 managed61.11% -> reject.
- V11 day gate: **64.71% / +0.563R / RR1.412**, but only17 trades -> supporting, not promotion.
- V12 legacy F4 path gate:27.91% -> reject.
- V13 genuine H+3/H+6/H+12 management: zero CUTs; stayed62.07% -> no improvement.
- V14 independent BUY/SELL: BUY dev88.24% but validation53.33%; SELL disabled -> reject/overfit.

Later F11 Jun08–12 is aggregate/day-level only, not feature-complete per trade. No untouched per-trade Forex block remains in the repo for an honest new selective validation. Further tuning existing May outcomes is development-only.

# Crypto
Canonical base remains **V24/Apr16** and the 61 symbol-specific linked-driver profiles.

## Parser correction
The old generic `extract_crypto()` lineage did not always inherit parent/day breadth/regime context correctly. Therefore V28–V33 must not be used as canonical promotion evidence where they rely on those inherited fields. Correct parser design follows `offline_crypto_regime_optimizer_v3_fast.py`. V35 uses corrected context inheritance.

## Best clean new branch — FLOW_AVAILABLE
V34 Jul02 -> Jul04:
- later frozen Jul04 filter: **37 trades, 78.38% WR, +0.959R, RR1.5**.

V34C focused flow branch, also selected only on Jul02 and frozen on Jul04:
- dev:10 trades,70.00%,+0.750R,RR1.5;
- later validation: **24 trades,19W/5L = 79.17% WR, +0.979R, RR1.5**.
This is the closest clean Crypto result to the requested number, but it is still below 80% and only one later validation date. Jul04 is now revealed; do not retune on it and call the result blind.

V35 corrected symbol/regime expanding WF:
-28 selected trades/6 dates,8W/20L=28.57%,-0.286R,RR1.5 -> reject as replacement.

Crypto modes going forward:
1. `FLOW_AVAILABLE`: preserve V24/V34/V34C fresh-flow lineage.
2. `FLOW_MISSING`: BTC+breadth/regime + HTF + M15/M5 + symbol-specific linked drivers + aggressive NO TRADE.

# Rolling HOLD/CUT
After MARKET/LIMIT fill, desired research mechanism remains sequential H+1/H+2/H+3... using only state known at each checkpoint. CUT is excluded from TP/SL WR by user convention but CUT stats and total expectancy remain mandatory.

Old Crypto rows lack hourly snapshots. Forex V13 honestly tested available H+3/H+6/H+12 checkpoints and generated zero useful CUTs. Never fabricate CUT from final outcome/MFE/MAE.

# Integrity boundary
At this point all feature-complete historical blocks suitable for these new hypotheses are revealed. Further parameter changes on the same rows can be diagnostics/development, but **cannot legitimately establish a new 80% held-out method**. For a new promotion test, freeze the next hypothesis first, then test on a new untouched block with entry features and hourly review snapshots.

## New-chat instruction
`Tiếp tục Trading từ checkpoint GitHub mới nhất. Đọc ITERATIVE_80WR_RESEARCH_V2.md. Forex best non-trivial held-out = V7 62.07% / +0.502R / RR1.407; V11=64.71% nhưng n17. Crypto FLOW_AVAILABLE best clean later validation = V34C 79.17% / +0.979R / RR1.5 trên24 lệnh; vẫn dưới80 và chỉ1 ngày. V28–V33 generic-parser results không được promote. Không được tiếp tục vặn các holdout đã lộ rồi gọi là blind.`
