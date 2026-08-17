# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 15:46 UTC+7

Read `MASTER_TRADING_STATE.md`, then `CROSSMARKET_ROLLING_BLIND_V6.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, then the relevant market checkpoint.

## Immediate active task
Improve BOTH Forex and Crypto entry quality toward TP/SL WR >=80% with average RR 1.0–1.5, using blind/held-out evidence and rolling HOLD/CUT management after fill. Latest V4/V5/V6 research used **0 market-data provider credits**.

Hourly review means a BACKTEST mechanism: once MARKET fills or LIMIT fills, advance historical time sequentially H+1/H+2/H+3... and decide HOLD/CUT using only data observable up to that review. No recurring automation is part of this research.

## Current result — target NOT reached
Do not claim 80% has been achieved.

### Forex broad benchmark
F8 remains frozen broad benchmark: four consecutive 5-day blocks /560 forced signals; MARKET 489 resolved, 248 TP /241 SL = 50.72% WR, weighted expectancy ~+0.233R. Typical RR ~1.42–1.45.

### Forex strongest selective-entry candidate
V5 fixed-rule, frozen on May18–22 and validated unchanged on May25–29.
Rule: BUY only, score >=1, ADX >=20, impulseEvidence >=3, H1 aligned; group/mode unrestricted.

Development:
- 31 trades;
- 23W /8L = 74.19% WR;
- +0.794R;
- avg RR 1.437.

Untouched validation:
- 28 trades;
- **17W /11L = 60.71% WR**;
- **+0.467R**;
- **avg RR 1.403**;
- positive-day rate 75%.

This is the strongest new legitimate selective-entry improvement, but F8 remains the broad benchmark and V5 is NOT an 80% method.

H+3 proxy rule (-0.4R) made zero CUTs in development and validation, so it did not improve V5. Exact H+1/H+2 management remains untestable from old data because those snapshots were not committed.

### Rejected Forex latest variants
- V4.1 daily changing threshold rule: 36.00% WR, -0.142R on forward-selected sample.
- V6 frozen confidence Top-5/day: development 60%, validation 40%; rejected.

## Crypto status
Recovered 640 old trades /12 dates, 35.78% baseline WR. Static/selective rules still fail to generalize.

V5 frozen rule validation:
- 31 trades;
- 6W /25L = **19.35% WR**;
- -0.516R;
- RR 1.5.
Rejected.

V6 frozen Top-8/day validation:
- 48 trades;
- 18W /30L = **37.50% WR**;
- -0.062R;
- RR 1.5.
Rejected.

Crypto live/research entry must continue to prioritize current BTC + breadth/regime + HTF structure + M15/M5 path + genuinely fresh flow/news rather than static symbol/macro reputation.

## Rolling-management data limitation
Old committed Forex/Crypto JSONs do not preserve full H+1/H+2 price + indicator + point-in-time news/calendar snapshots for every trade. Do not invent these snapshots or derive CUTs from final MFE/MAE/outcomes. Forex F8-style rows support only a limited genuine H+3 close checkpoint proxy.

## Promotion rule
Only report success when genuinely held-out managed evidence reaches all:
1. TP/SL WR >=80%;
2. average planned/effective RR 1.0–1.5;
3. positive expectancy including CUT;
4. non-trivial sample;
5. HOLD/CUT decisions based only on observable review-time state.

## Latest research files/runs
- `docs/checkpoints/CROSSMARKET_ROLLING_BLIND_V6.md`
- `scripts/offline_crossmarket_rolling_blind_v4.py` — run `32011504773`
- `scripts/offline_crossmarket_fixed_rule_v5.py` — successful run `32011669871`
- `scripts/offline_crossmarket_topk_v6.py` — run `32011803613`

## New-chat instruction
`Tiếp tục dự án Trading từ GitHub checkpoint mới nhất. Đọc MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, CROSSMARKET_ROLLING_BLIND_V6.md và TRADE_MANAGEMENT_HOURLY_V1.md. F8 là broad Forex baseline; V5 selective-entry đang tốt nhất với 60.71% WR / +0.467R / RR1.403; Crypto chưa có gate ổn định; không được nói 80% đã đạt.`
