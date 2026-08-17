# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 14:55 UTC+7

Read `MASTER_TRADING_STATE.md` first, then this file, then the relevant market checkpoint. Do not reconstruct strategy state from memory when checkpoints exist.

## Immediate active task
Forex method development. Research benchmark forces BUY/SELL on all 28 pairs; no Top-3/NO-TRADE in benchmark. **F8 factor-coherence + session + pair-archetype is the frozen research baseline**, now positive across four consecutive chronological 5-day validation blocks without changing the engine.

## F8 frozen architecture
Minimal indicators: EMA20/50, RSI14, ATR14, ADX14.
Main edge comes from:
- 3h/6h/12h/24h/72h currency-factor coherence;
- cross-sectional dispersion/rank separation;
- 8h session location/breakout/sweep;
- five pair archetypes;
- horizon-matched SL/TP/expiry.

Frozen archetype models:
- USD_MAJOR -> FACTOR_BAL
- JPY_CROSS -> SESSION_SWEEP
- EUROPE_CROSS -> FACTOR_BAL
- COMMODITY_CROSS -> FACTOR_FAST
- MIXED_CROSS -> FACTOR_BAL

## Four consecutive frozen F8 blocks
### May18–22
MARKET 58 TP /69 SL, +0.111R. LIMIT +0.030R.
### May25–29
MARKET 61 TP /50 SL, +0.338R. LIMIT +0.435R. Recommended +0.333R.
### Jun01–05
MARKET 66 TP /63 SL, +0.247R. LIMIT +0.325R. Recommended +0.252R.
### Jun08–12
F11 development gate selected no change (`selectedThreshold=null`), so this is another frozen-F8 holdout.
MARKET 63 TP /59 SL, +0.251R. LIMIT +0.199R. Recommended +0.267R.

## Combined frozen-F8 evidence
20 trading days / 560 forced signals.
MARKET:
- 489 resolved;
- 248 TP /241 SL;
- WR **50.72%**;
- weighted expectancy ~**+0.233R**.

LIMIT:
- 403 resolved;
- 169 TP /234 SL;
- WR 41.94%;
- weighted expectancy ~**+0.246R**.

Recommended execution:
- 487 resolved;
- 247 TP /240 SL;
- WR 50.72%;
- weighted expectancy ~**+0.237R**.

Combined direction across 560 signals:
- chosen 58.57%;
- 3h 59.64%;
- 6h 55.36%;
- 12h 55.54%;
- 24h 53.21%.

F8 is the strongest Forex evidence so far, but forced-all-pair success remains research evidence, not a mandate to trade every pair live.

## Latest rejected/no-change improvements
- F9 three-horizon: positive but inferior to F8 on same May25–29 block.
- F10 USD_MID: development improvement did not clear the predeclared selection margin, so F8 stayed unchanged; USD_MAJOR then performed +0.399R on Jun01–05.
- F10 leave-one-pair-out factor network: MARKET +0.239R vs F8 +0.247R on same Jun01–05; direction unchanged. Self-inclusion is not the issue.
- F11 day-conflict MID_FACTOR: thresholds 0.55/0.65/0.75 activated zero development days, therefore no model change; do not lower thresholds on revealed data.

## Main remaining weakness
**Catastrophic common-factor/date regime failure** rather than one consistently bad pair group.
Example Jun04:
- 5 TP /22 SL;
- MARKET -0.565R;
- direction12/24 21.43%;
- 19/22 SL were true bias-wrong.
F8 still kept Jun01–05 positive overall, but reducing this tail-day failure is the next meaningful research target.

## Next research rule
Freeze F8. Any new common-factor/day-regime hypothesis must:
1. be defined using revealed data only;
2. be locked before a new untouched block;
3. compare modified method vs frozen F8 on the SAME 28-pair block;
4. keep all 28 pairs forced in benchmark;
5. add no redundant indicators;
6. be rejected if it does not materially beat F8.

## Live Forex rule
Forced benchmark does not imply live forced trading. Live entry still requires:
- fresh exact pair price;
- currency-specific macro/news context;
- F8 factor/archetype state;
- H4/H1 structure;
- M15 setup;
- M5 trigger;
- structural SL and realistic horizon/liquidity target;
- setup-dependent MARKET vs LIMIT.

## Twelve Data efficiency
One M15 history per 28 pairs ≈28 symbol credits/block; H1/H4/features derived locally. Reuse data for model comparisons; workflows share quota concurrency + cooldown.

## Active Forex files
- `scripts/blind_backtest_forex_f8.py`
- `data/blind_backtest_forex_f8.json`
- `data/blind_backtest_forex_f8_holdout2.json`
- `data/blind_backtest_forex_f10_loo.json`
- `data/blind_backtest_forex_f10_usd_mid.json`
- `data/blind_backtest_forex_f11_day_conflict.json`
- `docs/checkpoints/FOREX_STATE.md`

## New-chat instruction
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc docs/checkpoints/MASTER_TRADING_STATE.md và docs/checkpoints/CURRENT_HANDOFF.md trước, sau đó đọc checkpoint thị trường liên quan.`
