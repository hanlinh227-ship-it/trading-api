# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 15:33 UTC+7

Read `MASTER_TRADING_STATE.md`, `CROSSMARKET_80WR_OFFLINE_AUDIT.md`, `TRADE_MANAGEMENT_HOURLY_V1.md`, then the relevant market checkpoint.

## Immediate active task
Develop a managed-entry method for BOTH Forex and Crypto. No real recurring schedule/automation is part of this test. Hourly review is simulated/researched as H+1/H+2/H+3... HOLD/CUT logic after a MARKET or LIMIT order has filled.

## Required method
Before entry incorporate current news/macro, economic/event calendar, regime/bias, structure, setup, execution type, structural SL and realistic TP. New target track wants average planned/effective RR 1.0–1.5.

After fill, each hourly review must use only information observable at that hour: exact price/time, fresh news, calendar/event risk, H1/M15/M5 path, indicator/factor/regime state and distance to original invalidation/target. Decision = HOLD or CUT.

Statistics:
- TP and SL form displayed win rate: TP/(TP+SL).
- CUT is excluded from that WR by user convention.
- But every report MUST also show CUT count/rate, average CUT R, and total expectancy including CUT. Do not manufacture 80% by cutting losses after seeing outcomes.

## Forex comparator
Frozen F8 remains strongest evidence: 20 trading days /560 forced signals, MARKET 489 resolved, 248 TP /241 SL = 50.72% WR, weighted expectancy ~+0.233R. Typical F8 RR evidence ~1.42–1.45 already lies inside the requested 1.0–1.5 track.

## Crypto comparator
Recovered 12-date set: 640 resolved, 229 TP /411 SL = 35.78% WR, -0.057R, average RR 1.639. Crypto selection remains BTC + breadth/regime + HTF structure + M15/M5 path; static symbol reputation is rejected.

## Managed-entry feasibility audit
Zero-provider run `32010580143` completed successfully.
Oracle-only burden to display 80% WR if every CUT magically removes a loser and never removes a winner:
- Forex: must CUT 179/241 losses = 74.27%, leaving 248 TP /62 SL = 80.00%.
- Crypto: must CUT 354/411 losses = 86.13%, leaving 229 TP /57 SL = 80.07%.
These are impossible hindsight-perfect upper bounds, NOT validation.

## Historical limitation
Old blind JSONs generally lack complete H+1/H+2 price + indicator + point-in-time news/calendar snapshots. Therefore a true historical hourly HOLD/CUT blind validation cannot be reconstructed across all old blocks without missing data. Do not infer historical news or use future-direction/outcome fields as if they were observable hourly signals.

## Promotion rule
Only report success when a genuinely blind/held-out managed dataset reaches:
1. TP/SL WR >=80%;
2. average planned/effective RR 1.0–1.5;
3. positive total expectancy including CUT;
4. non-trivial sample;
5. hourly decisions based on genuinely observable snapshots.

## New-chat instruction
`Tiếp tục dự án Trading từ GitHub checkpoint mới nhất. Đọc MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, CROSSMARKET_80WR_OFFLINE_AUDIT.md và TRADE_MANAGEMENT_HOURLY_V1.md. Không được nói 80% đã đạt; hourly HOLD/CUT hiện là research protocol, không phải lịch tự động.`
